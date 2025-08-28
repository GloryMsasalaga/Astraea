# security/authentication.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from .models import UserProfile, AuditLog, SecurityAlert, PasswordHistory
import pyotp
import qrcode
import io
import base64

class SecureAuthenticationBackend(ModelBackend):
    """Enhanced authentication backend with security features"""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Log failed attempt
            self.log_failed_attempt(request, username, 'user_not_found')
            return None
        
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Check if account is locked
        if profile.is_account_locked():
            self.log_failed_attempt(request, username, 'account_locked')
            return None
        
        # Check password
        if user.check_password(password):
            # Reset failed attempts on successful login
            profile.failed_login_attempts = 0
            profile.save()
            
            # Check if 2FA is enabled
            if profile.two_factor_enabled:
                # Store user in session for 2FA verification
                if request:
                    request.session['pre_2fa_user_id'] = user.id
                return None  # Don't complete login yet
            
            # Log successful login
            self.log_successful_login(request, user)
            return user
        else:
            # Increment failed attempts
            profile.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if profile.failed_login_attempts >= 5:
                profile.lock_account(duration_minutes=30)
                
                # Create security alert
                SecurityAlert.objects.create(
                    alert_type='multiple_failed_logins',
                    risk_level='high',
                    user=user,
                    ip_address=self.get_client_ip(request) if request else None,
                    description=f'Account locked after {profile.failed_login_attempts} failed attempts',
                    details={'failed_attempts': profile.failed_login_attempts}
                )
            
            profile.save()
            self.log_failed_attempt(request, username, 'invalid_password')
            return None
    
    def verify_2fa(self, request, user, token):
        """Verify 2FA token"""
        try:
            profile = UserProfile.objects.get(user=user)
            
            if not profile.two_factor_enabled or not profile.two_factor_secret:
                return False
            
            totp = pyotp.TOTP(profile.two_factor_secret)
            if totp.verify(token, valid_window=1):
                # Remove pre-2FA session data
                if 'pre_2fa_user_id' in request.session:
                    del request.session['pre_2fa_user_id']
                
                self.log_successful_login(request, user)
                return True
            else:
                self.log_failed_attempt(request, user.username, '2fa_failed')
                return False
                
        except UserProfile.DoesNotExist:
            return False
    
    def setup_2fa(self, user):
        """Set up 2FA for a user"""
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if not profile.two_factor_secret:
            profile.two_factor_secret = pyotp.random_base32()
            profile.save()
        
        # Generate QR code
        totp = pyotp.TOTP(profile.two_factor_secret)
        provisioning_uri = totp.provisioning_uri(
            user.email,
            issuer_name="AuditFlow"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            'secret': profile.two_factor_secret,
            'qr_code': qr_code_data,
            'manual_entry_key': profile.two_factor_secret
        }
    
    def enable_2fa(self, user, verification_token):
        """Enable 2FA after verifying the setup"""
        try:
            profile = UserProfile.objects.get(user=user)
            
            if not profile.two_factor_secret:
                return False
            
            totp = pyotp.TOTP(profile.two_factor_secret)
            if totp.verify(verification_token, valid_window=1):
                profile.two_factor_enabled = True
                profile.save()
                
                AuditLog.objects.create(
                    user=user,
                    action='settings_change',
                    severity='medium',
                    ip_address='127.0.0.1',  # Will be updated by middleware
                    user_agent='System',
                    details={'change': '2FA enabled'}
                )
                return True
            
            return False
            
        except UserProfile.DoesNotExist:
            return False
    
    def disable_2fa(self, user, current_password):
        """Disable 2FA with password verification"""
        if not user.check_password(current_password):
            return False
        
        try:
            profile = UserProfile.objects.get(user=user)
            profile.two_factor_enabled = False
            profile.two_factor_secret = ''
            profile.save()
            
            AuditLog.objects.create(
                user=user,
                action='settings_change',
                severity='medium',
                ip_address='127.0.0.1',  # Will be updated by middleware
                user_agent='System',
                details={'change': '2FA disabled'}
            )
            return True
            
        except UserProfile.DoesNotExist:
            return False
    
    def change_password(self, user, old_password, new_password):
        """Change password with security checks"""
        if not user.check_password(old_password):
            return {'success': False, 'error': 'Current password is incorrect'}
        
        # Check password history (prevent reuse of last 5 passwords)
        password_histories = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:5]
        
        for history in password_histories:
            if check_password(new_password, history.password_hash):
                return {'success': False, 'error': 'Cannot reuse recent passwords'}
        
        # Validate password strength
        validation_result = self.validate_password_strength(new_password)
        if not validation_result['valid']:
            return {'success': False, 'error': validation_result['message']}
        
        # Save old password to history
        PasswordHistory.objects.create(
            user=user,
            password_hash=user.password
        )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.password_changed_at = timezone.now()
        profile.save()
        
        # Log password change
        AuditLog.objects.create(
            user=user,
            action='password_change',
            severity='medium',
            ip_address='127.0.0.1',  # Will be updated by middleware
            user_agent='System',
            details={'timestamp': timezone.now().isoformat()}
        )
        
        return {'success': True, 'message': 'Password changed successfully'}
    
    def validate_password_strength(self, password):
        """Validate password strength"""
        if len(password) < 8:
            return {'valid': False, 'message': 'Password must be at least 8 characters long'}
        
        if not any(c.isupper() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one uppercase letter'}
        
        if not any(c.islower() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one lowercase letter'}
        
        if not any(c.isdigit() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one digit'}
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            return {'valid': False, 'message': 'Password must contain at least one special character'}
        
        return {'valid': True, 'message': 'Password meets security requirements'}
    
    def log_successful_login(self, request, user):
        """Log successful login"""
        AuditLog.objects.create(
            user=user,
            action='login',
            severity='low',
            ip_address=self.get_client_ip(request) if request else '127.0.0.1',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request else 'System',
            details={'timestamp': timezone.now().isoformat()}
        )
    
    def log_failed_attempt(self, request, username, reason):
        """Log failed login attempt"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        
        AuditLog.objects.create(
            user=user,
            action='login_failed',
            severity='medium' if reason == 'account_locked' else 'low',
            ip_address=self.get_client_ip(request) if request else '127.0.0.1',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request else 'System',
            details={'username': username, 'reason': reason}
        )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        if not request:
            return '127.0.0.1'
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
