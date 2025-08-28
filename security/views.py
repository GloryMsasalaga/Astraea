# security/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)
from .authentication import SecureAuthenticationBackend
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
import json
import pyotp
import qrcode
import io
import base64
from .models import UserProfile, AuditLog, SecurityAlert, UserSession
from .forms import SecureLoginForm, TwoFactorForm, PasswordChangeSecureForm, SecureRegistrationForm


class SecurityDashboardView(LoginRequiredMixin, TemplateView):
    """Security dashboard showing user's security status and recent activity"""
    template_name = 'security/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get recent security alerts
        context['recent_alerts'] = SecurityAlert.objects.filter(
            user=user,
            is_resolved=False
        ).order_by('-created_at')[:5]
        
        # Get active sessions
        context['active_sessions'] = UserSession.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_activity')
        
        # Get recent activity from audit log
        context['recent_activity'] = AuditLog.objects.filter(
            user=user
        ).order_by('-timestamp')[:10]
        
        return context


class SecureLoginView(FormView):
    """Enhanced login view with security features"""
    template_name = 'registration/login.html'
    form_class = SecureLoginForm
    
    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        try:
            logger.info(f'Login attempt for user: {username}')  # Log login attempt
            # Use custom authentication backend
            backend = SecureAuthenticationBackend()
            user = backend.authenticate(self.request, username=username, password=password)
            if user:
                # Set the backend attribute on the user object
                user.backend = 'security.authentication.SecureAuthenticationBackend'
                # Check if 2FA is enabled
                if hasattr(user, 'userprofile') and user.userprofile.two_factor_enabled:
                    logger.info(f'User {username} has 2FA enabled, redirecting to 2FA verification')
                    self.request.session['pre_2fa_user_id'] = user.id
                    self.request.session['pre_2fa_username'] = username
                    return redirect('security:2fa_verify')
                else:
                    logger.info(f'User {username} logged in successfully, redirecting to dashboard')
                    login(self.request, user)
                    AuditLog.objects.create(
                        user=user,
                        action='login',
                        severity='low',
                        ip_address=self.get_client_ip(),
                        user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                        details={
                            'username': user.username,
                            'login_time': timezone.now().isoformat(),
                            'ip_address': self.get_client_ip()
                        }
                    )
                    UserSession.objects.get_or_create(
                        user=user,
                        session_key=self.request.session.session_key,
                        defaults={
                            'ip_address': self.get_client_ip(),
                            'user_agent': self.request.META.get('HTTP_USER_AGENT', '')[:500]
                        }
                    )
                    messages.success(self.request, 'Welcome back! You have been logged in successfully.')
                    next_url = self.request.GET.get('next', None)
                    if next_url:
                        logger.info(f'Redirecting to next URL: {next_url}')  # Log redirect
                        return redirect(next_url)
                    else:
                        logger.info('Redirecting to dashboard')  # Log redirect
                        return redirect('security:dashboard')
            else:
                logger.warning(f'Login failed for user: {username}')  # Log failed login
                AuditLog.objects.create(
                    user=None,
                    action='login_failed',
                    severity='medium',
                    ip_address=self.get_client_ip(),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                    details={
                        'username': username,
                        'login_attempt_time': timezone.now().isoformat(),
                        'ip_address': self.get_client_ip()
                    }
                )
                # Set form errors so the template displays them
                form.add_error('username', '')
                form.add_error('password', 'Invalid username or password.')
                messages.error(self.request, 'Invalid username or password.')
                return self.form_invalid(form)
        except Exception as e:
            logger.error(f'Login error for user: {username}, Error: {str(e)}')  # Log error
            messages.error(self.request, f'Login error: {str(e)}')
            return redirect('security:login')
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class SecureRegistrationView(FormView):
    """Enhanced registration view with security features"""
    template_name = 'registration/register.html'
    form_class = SecureRegistrationForm
    success_url = '/dashboard/'
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect authenticated users
        if request.user.is_authenticated:
            return redirect('security:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        try:
            user = form.save()
            AuditLog.objects.create(
                user=user,
                action='user_registered',
                severity='low',
                ip_address=self.get_client_ip(),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'username': user.username,
                    'email': user.email,
                    'registration_time': timezone.now().isoformat(),
                    'ip_address': self.get_client_ip()
                }
            )
            SecurityAlert.objects.create(
                user=user,
                alert_type='account_created',
                risk_level='low',
                description=f'Welcome to AuditFlow! Your account has been created successfully.',
                ip_address=self.get_client_ip(),
                details={
                    'registration_time': timezone.now().isoformat(),
                    'welcome_message': True
                }
            )
            messages.success(
                self.request,
                'Registration successful! You can now log in with your credentials.'
            )
            login(self.request, user)
            return redirect('security:dashboard')
        except Exception as e:
            messages.error(self.request, f'Registration error: {str(e)}')
            return redirect('security:register')
    
    def form_invalid(self, form):
        # Log failed registration attempt
        AuditLog.objects.create(
            user=None,
            action='registration_failed',
            severity='medium',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            details={
                'username': form.cleaned_data.get('username', ''),
                'email': form.cleaned_data.get('email', ''),
                'errors': form.errors.as_json(),
                'ip_address': self.get_client_ip()
            }
        )
        
        messages.error(
            self.request,
            'Registration failed. Please correct the errors below.'
        )
        return super().form_invalid(form)
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class SecureLogoutView(LoginRequiredMixin, TemplateView):
    """Secure logout view"""
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Log logout
        AuditLog.objects.create(
            user=user,
            action='logout',
            severity='low',
            ip_address=self.get_client_ip(),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={
                'logout_time': timezone.now().isoformat(),
                'ip_address': self.get_client_ip()
            }
        )
        
        # Deactivate user session
        UserSession.objects.filter(
            user=user,
            session_key=request.session.session_key
        ).update(is_active=False)
        
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('security:login')
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorSetupView(LoginRequiredMixin, TemplateView):
    """Setup two-factor authentication"""
    template_name = 'security/2fa_setup.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Generate TOTP secret if not exists
        if not hasattr(user, 'userprofile') or not user.userprofile.totp_secret:
            secret = pyotp.random_base32()
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.totp_secret = secret
            profile.save()
        else:
            secret = user.userprofile.totp_secret
        
        # Generate QR code
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name='AuditFlow'
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        context['qr_code'] = qr_code_b64
        context['secret_key'] = secret
        
        return context
    
    def post(self, request, *args, **kwargs):
        verification_token = request.POST.get('verification_token')
        user = request.user
        
        if verification_token:
            # Verify the token
            profile = user.userprofile
            totp = pyotp.TOTP(profile.totp_secret)
            
            if totp.verify(verification_token, valid_window=1):
                # Enable 2FA
                profile.two_factor_enabled = True
                profile.save()
                
                # Log 2FA setup
                AuditLog.objects.create(
                    user=user,
                    action='2fa_enabled',
                    severity='low',
                    ip_address=self.get_client_ip(),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    details={
                        'setup_time': timezone.now().isoformat(),
                        'ip_address': self.get_client_ip()
                    }
                )
                
                messages.success(request, 'Two-factor authentication has been enabled successfully!')
                return redirect('security:dashboard')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        
        return self.get(request, *args, **kwargs)
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorVerifyView(FormView):
    """Verify two-factor authentication token"""
    template_name = 'security/2fa_verify.html'
    form_class = TwoFactorForm
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is in 2FA verification state
        if 'pre_2fa_user_id' not in request.session:
            return redirect('security:login')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        token = form.cleaned_data['token']
        user_id = self.request.session.get('pre_2fa_user_id')
        
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
            profile = user.userprofile
            
            logger.info(f'2FA verification attempt for user ID: {user_id}')  # Log 2FA attempt
            
            # Verify TOTP token
            totp = pyotp.TOTP(profile.totp_secret)
            if totp.verify(token, valid_window=1):
                logger.info(f'2FA verification successful for user: {user.username}')  # Log success
                # Set the backend attribute on the user object
                user.backend = 'security.authentication.SecureAuthenticationBackend'
                
                # Complete login
                login(self.request, user)
                
                # Clean up session
                del self.request.session['pre_2fa_user_id']
                if 'pre_2fa_username' in self.request.session:
                    del self.request.session['pre_2fa_username']
                
                # Log successful 2FA login
                AuditLog.objects.create(
                    user=user,
                    action='2fa_login',
                    severity='low',
                    ip_address=self.get_client_ip(),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                    details={
                        'login_time': timezone.now().isoformat(),
                        'ip_address': self.get_client_ip()
                    }
                )
                
                # Create user session record
                UserSession.objects.create(
                    user=user,
                    session_key=self.request.session.session_key,
                    ip_address=self.get_client_ip(),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                
                messages.success(self.request, 'Two-factor authentication successful. Welcome back!')
                logger.info(f'User {user.username} logged in successfully via 2FA, redirecting to dashboard')  # Log redirect
                return redirect('security:dashboard')
            else:
                logger.warning(f'2FA verification failed for user: {user.username}')  # Log failed 2FA
                # Log failed 2FA attempt
                AuditLog.objects.create(
                    user=user,
                    action='2fa_failed',
                    severity='medium',
                    ip_address=self.get_client_ip(),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                    details={
                        'attempt_time': timezone.now().isoformat(),
                        'ip_address': self.get_client_ip()
                    }
                )
                
                messages.error(self.request, 'Invalid verification code. Please try again.')
                return self.form_invalid(form)
                
        except Exception as e:
            logger.error(f'2FA verification error for user ID: {user_id}, Error: {str(e)}')  # Log error
            messages.error(self.request, 'An error occurred during verification.')
            return redirect('security:login')
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class TwoFactorDisableView(LoginRequiredMixin, TemplateView):
    """Disable two-factor authentication"""
    
    def post(self, request, *args, **kwargs):
        user = request.user
        
        if hasattr(user, 'userprofile'):
            profile = user.userprofile
            profile.two_factor_enabled = False
            profile.totp_secret = ''
            profile.save()
            
            # Log 2FA disable
            AuditLog.objects.create(
                user=user,
                action='2fa_disabled',
                severity='low',
                ip_address=self.get_client_ip(),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'disable_time': timezone.now().isoformat(),
                    'ip_address': self.get_client_ip()
                }
            )
            
            messages.success(request, 'Two-factor authentication has been disabled.')
        
        return redirect('security:dashboard')
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class PasswordChangeSecureView(LoginRequiredMixin, FormView):
    """Secure password change with enhanced validation"""
    template_name = 'security/change_password.html'
    form_class = PasswordChangeSecureForm
    
    def form_valid(self, form):
        user = self.request.user
        old_password = form.cleaned_data['old_password']
        new_password = form.cleaned_data['new_password1']
        
        # Verify old password
        if not user.check_password(old_password):
            messages.error(self.request, 'Current password is incorrect.')
            return self.form_invalid(form)
        
        # Change password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(self.request, user)
        
        # Log password change
        AuditLog.objects.create(
            user=user,
            action='password_change',
            severity='low',
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            details={
                'change_time': timezone.now().isoformat(),
                'ip_address': self.get_client_ip()
            }
        )
        
        messages.success(self.request, 'Your password has been changed successfully.')
        return redirect('security:dashboard')
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class PasswordResetSecureView(TemplateView):
    """Secure password reset view"""
    template_name = 'security/password_reset.html'
    
    def post(self, request, *args, **kwargs):
        # Implementation for password reset
        # This would typically involve sending an email with a reset link
        messages.info(request, 'Password reset functionality will be implemented.')
        return render(request, 'security/change_password.html')


class SecurityAlertsView(LoginRequiredMixin, TemplateView):
    """View security alerts for the user"""
    template_name = 'security/alerts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        alerts = SecurityAlert.objects.filter(user=user).order_by('-created_at')
        
        # Pagination
        paginator = Paginator(alerts, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['alerts'] = page_obj
        
        return context


class ActiveSessionsView(LoginRequiredMixin, TemplateView):
    """View active sessions for the user"""
    template_name = 'security/sessions.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        sessions = UserSession.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_activity')
        
        # Mark current session
        current_session_key = self.request.session.session_key
        for session in sessions:
            session.is_current = session.session_key == current_session_key
        
        context['sessions'] = sessions
        
        return context


class AuditLogView(LoginRequiredMixin, TemplateView):
    """View audit log for the user"""
    template_name = 'security/audit_log.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        audit_logs = AuditLog.objects.filter(user=user).order_by('-timestamp')
        
        # Pagination
        paginator = Paginator(audit_logs, 50)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['audit_logs'] = page_obj
        
        return context


# AJAX Views
@login_required
@require_POST
def resolve_alert(request, alert_id):
    """Resolve a security alert"""
    try:
        alert = get_object_or_404(SecurityAlert, id=alert_id, user=request.user)
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def terminate_session(request, session_key):
    """Terminate a user session"""
    try:
        session = get_object_or_404(
            UserSession, 
            session_key=session_key, 
            user=request.user,
            is_active=True
        )
        
        # Don't allow terminating current session
        if session_key == request.session.session_key:
            return JsonResponse({'success': False, 'error': 'Cannot terminate current session'})
        
        session.is_active = False
        session.save()
        
        # Log session termination
        AuditLog.objects.create(
            user=request.user,
            action='session_terminated',
            severity='low',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={
                'terminated_session': session_key[:8] + '...',
                'termination_time': timezone.now().isoformat(),
                'ip_address': get_client_ip(request)
            }
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def check_password_strength(request):
    """API endpoint to check password strength"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
            
            # Simple password strength check
            score = 0
            if len(password) >= 8:
                score += 25
            if any(c.isupper() for c in password):
                score += 25
            if any(c.islower() for c in password):
                score += 25
            if any(c.isdigit() for c in password):
                score += 25
            
            return JsonResponse({
                'score': score,
                'strength': 'weak' if score < 50 else 'medium' if score < 75 else 'strong'
            })
        except:
            pass
    
    return JsonResponse({'score': 0, 'strength': 'weak'})


@login_required
def security_status(request):
    """API endpoint to get security status"""
    user = request.user
    
    status = {
        'two_factor_enabled': False,
        'account_locked': False,
        'failed_attempts': 0,
        'last_login': None,
        'active_alerts': 0
    }
    
    if hasattr(user, 'userprofile'):
        profile = user.userprofile
        status.update({
            'two_factor_enabled': profile.two_factor_enabled,
            'account_locked': profile.account_locked,
            'failed_attempts': profile.failed_login_attempts,
        })
    
    if user.last_login:
        status['last_login'] = user.last_login.isoformat()
    
    status['active_alerts'] = SecurityAlert.objects.filter(
        user=user,
        is_resolved=False
    ).count()
    
    return JsonResponse(status)


def get_client_ip(request):
    """Helper function to get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
