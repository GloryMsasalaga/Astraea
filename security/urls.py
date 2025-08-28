from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Security Dashboard
    path('', views.SecurityDashboardView.as_view(), name='dashboard'),
    
    # Authentication Views
    path('register/', views.SecureRegistrationView.as_view(), name='register'),
    path('login/', views.SecureLoginView.as_view(), name='login'),
    path('logout/', views.SecureLogoutView.as_view(), name='logout'),
    
    # Two-Factor Authentication
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/verify/', views.TwoFactorVerifyView.as_view(), name='2fa_verify'),
    path('2fa/disable/', views.TwoFactorDisableView.as_view(), name='2fa_disable'),
    
    # Password Management
    path('change-password/', views.PasswordChangeSecureView.as_view(), name='change_password'),
    path('reset-password/', views.PasswordResetSecureView.as_view(), name='reset_password'),
    
    # Security Management
    path('alerts/', views.SecurityAlertsView.as_view(), name='alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
    path('sessions/', views.ActiveSessionsView.as_view(), name='sessions'),
    path('sessions/<str:session_key>/terminate/', views.terminate_session, name='terminate_session'),
    path('audit-log/', views.AuditLogView.as_view(), name='audit_log'),
    
    # API Endpoints
    path('api/check-password-strength/', views.check_password_strength, name='check_password_strength'),
    path('api/security-status/', views.security_status, name='security_status'),
]
