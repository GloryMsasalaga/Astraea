# security/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .models import AuditLog, UserSession, SecurityAlert, UserProfile
import json

def get_client_ip(request):
    """Get the client's IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class AuditLogMiddleware(MiddlewareMixin):
    """Middleware to log all user actions for audit trail"""
    
    def process_request(self, request):
        # Store request start time for performance tracking
        request.audit_start_time = timezone.now()
        
        # Store IP and User Agent for logging
        request.client_ip = get_client_ip(request)
        request.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        return None
    
    def process_response(self, request, response):
        # Skip logging for static files and admin
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.path.startswith('/admin/')):
            return response
        
        # Log successful actions
        if hasattr(request, 'user') and request.user.is_authenticated:
            action = self.determine_action(request, response)
            if action:
                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    ip_address=request.client_ip,
                    user_agent=request.user_agent,
                    details={
                        'path': request.path,
                        'method': request.method,
                        'status_code': response.status_code,
                        'response_time': str(timezone.now() - request.audit_start_time),
                    }
                )
        
        return response
    
    def determine_action(self, request, response):
        """Determine what action to log based on request"""
        path = request.path
        method = request.method
        
        # Map URLs to actions
        if path == '/security/login/' and method == 'POST' and response.status_code == 302:
            return 'login'
        elif path == '/security/logout/':
            return 'logout'
        elif 'documents' in path and method == 'POST':
            return 'document_upload'
        elif 'documents' in path and method == 'GET' and 'download' in path:
            return 'document_download'
        elif 'transactions' in path and method == 'POST':
            return 'transaction_create'
        elif 'reconciliation' in path and method == 'POST':
            return 'reconciliation_create'
        elif 'reports' in path and method == 'POST':
            return 'report_generate'
        elif 'settings' in path and method == 'POST':
            return 'settings_change'
        elif 'export' in path:
            return 'export_data'
        
        return None

class SessionSecurityMiddleware(MiddlewareMixin):
    """Middleware for session security and tracking"""
    
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            session_key = request.session.session_key
            
            # Update or create session tracking
            user_session, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    'user': request.user,
                    'ip_address': get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                }
            )
            
            # Check for session hijacking (IP change)
            if not created and user_session.ip_address != get_client_ip(request):
                SecurityAlert.objects.create(
                    alert_type='session_hijacking',
                    risk_level='high',
                    user=request.user,
                    ip_address=get_client_ip(request),
                    description=f'Session IP changed from {user_session.ip_address} to {get_client_ip(request)}',
                    details={
                        'old_ip': str(user_session.ip_address),
                        'new_ip': get_client_ip(request),
                        'session_key': session_key,
                    }
                )
                
                # Log out user for security
                from django.contrib.auth import logout
                logout(request)
                return HttpResponseForbidden('Session security violation detected.')
            
            # Update session activity
            user_session.last_activity = timezone.now()
            user_session.save()
            
            # Check for expired sessions
            if user_session.is_expired():
                user_session.is_active = False
                user_session.save()
                from django.contrib.auth import logout
                logout(request)
                messages.warning(request, 'Your session has expired. Please log in again.')
                return redirect('login')
        
        return None

class AccountLockoutMiddleware(MiddlewareMixin):
    """Middleware to handle account lockouts"""
    
    def process_request(self, request):
        if request.path == '/login/' and request.method == 'POST':
            username = request.POST.get('username')
            if username:
                try:
                    user = User.objects.get(username=username)
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    
                    if profile.is_account_locked():
                        # Log failed attempt on locked account
                        AuditLog.objects.create(
                            user=user,
                            action='login_failed',
                            severity='medium',
                            ip_address=get_client_ip(request),
                            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                            details={'reason': 'Account locked'}
                        )
                        
                        messages.error(request, 'Account is temporarily locked due to multiple failed login attempts.')
                        return redirect('login')
                        
                except User.DoesNotExist:
                    # Log attempt with non-existent username
                    AuditLog.objects.create(
                        action='login_failed',
                        severity='low',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        details={'username': username, 'reason': 'User does not exist'}
                    )
        
        return None

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses"""
    
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # HTTPS enforcement in production
        if not request.is_secure() and hasattr(request, 'get_host'):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response

class AnomalyDetectionMiddleware(MiddlewareMixin):
    """Basic anomaly detection middleware"""
    
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            ip_address = get_client_ip(request)
            
            # Check for unusual activity patterns
            recent_logs = AuditLog.objects.filter(
                user=request.user,
                timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
            ).count()
            
            # Alert if too many actions in short time
            if recent_logs > 100:  # Threshold
                SecurityAlert.objects.create(
                    alert_type='unusual_activity',
                    risk_level='medium',
                    user=request.user,
                    ip_address=ip_address,
                    description=f'User performed {recent_logs} actions in the last hour',
                    details={'action_count': recent_logs, 'timeframe': '1 hour'}
                )
            
            # Check for login from new location
            if request.path == '/login/' and request.method == 'POST':
                previous_ips = AuditLog.objects.filter(
                    user=request.user,
                    action='login',
                    timestamp__gte=timezone.now() - timezone.timedelta(days=30)
                ).values_list('ip_address', flat=True).distinct()
                
                if ip_address not in previous_ips and previous_ips.exists():
                    SecurityAlert.objects.create(
                        alert_type='suspicious_login',
                        risk_level='medium',
                        user=request.user,
                        ip_address=ip_address,
                        description='Login from new IP address',
                        details={'new_ip': ip_address, 'known_ips': list(previous_ips)}
                    )
        
        return None
