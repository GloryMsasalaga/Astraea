# security/models.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
import hashlib
import json
from datetime import timedelta

class UserProfile(models.Model):
    """Extended user profile with security features"""
    ROLE_CHOICES = [
        ('accountant', 'Accountant'),
        ('auditor', 'Auditor'),
        ('manager', 'Manager'),
        ('viewer', 'Viewer'),
        ('admin', 'Administrator'),
        ('super_admin', 'Super Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    phone_number = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=100, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)
    last_password_change_reminder = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False
    
    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration"""
        self.account_locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save()
    
    def unlock_account(self):
        """Unlock the account"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save()

class AuditLog(models.Model):
    """Immutable audit trail for all system actions"""
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('login_failed', 'Failed Login Attempt'),
        ('password_change', 'Password Changed'),
        ('profile_update', 'Profile Updated'),
        ('document_upload', 'Document Uploaded'),
        ('document_download', 'Document Downloaded'),
        ('document_delete', 'Document Deleted'),
        ('transaction_create', 'Transaction Created'),
        ('transaction_update', 'Transaction Updated'),
        ('transaction_delete', 'Transaction Deleted'),
        ('reconciliation_create', 'Reconciliation Created'),
        ('reconciliation_update', 'Reconciliation Updated'),
        ('report_generate', 'Report Generated'),
        ('export_data', 'Data Exported'),
        ('settings_change', 'Settings Changed'),
        ('user_create', 'User Created'),
        ('user_update', 'User Updated'),
        ('user_deactivate', 'User Deactivated'),
        ('permission_change', 'Permissions Changed'),
        ('system_backup', 'System Backup'),
        ('system_restore', 'System Restore'),
        ('anomaly_detected', 'Anomaly Detected'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Generic foreign key for linking to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    affected_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional context
    details = models.JSONField(default=dict, blank=True)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    
    # Integrity protection
    checksum = models.CharField(max_length=64, editable=False)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def save(self, *args, **kwargs):
        # Generate checksum for integrity
        if not self.checksum:
            data = {
                'user_id': self.user.id if self.user else None,
                'action': self.action,
                'ip_address': str(self.ip_address),
                'timestamp': self.timestamp.isoformat() if self.timestamp else timezone.now().isoformat(),
                'details': self.details,
            }
            self.checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        super().save(*args, **kwargs)
    
    def verify_integrity(self):
        """Verify the integrity of this audit log entry"""
        data = {
            'user_id': self.user.id if self.user else None,
            'action': self.action,
            'ip_address': str(self.ip_address),
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
        }
        expected_checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return self.checksum == expected_checksum
    
    def __str__(self):
        return f"{self.get_action_display()} by {self.user} at {self.timestamp}"

class UserSession(models.Model):
    """Track active user sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"
    
    def is_expired(self, timeout_minutes=30):
        """Check if session has expired"""
        return timezone.now() - self.last_activity > timedelta(minutes=timeout_minutes)

class DocumentHash(models.Model):
    """Store document hashes for integrity verification"""
    document_id = models.IntegerField()  # Reference to document in documents app
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    sha256_hash = models.CharField(max_length=64, unique=True)
    md5_hash = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['document_id', 'sha256_hash']
    
    def __str__(self):
        return f"{self.filename} - {self.sha256_hash[:16]}..."

class SecurityAlert(models.Model):
    """Security alerts and anomaly detection"""
    ALERT_TYPES = [
        ('suspicious_login', 'Suspicious Login'),
        ('multiple_failed_logins', 'Multiple Failed Logins'),
        ('unusual_activity', 'Unusual Activity'),
        ('data_breach_attempt', 'Data Breach Attempt'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('anomaly_transaction', 'Anomalous Transaction'),
        ('file_integrity_violation', 'File Integrity Violation'),
        ('session_hijacking', 'Session Hijacking'),
        ('account_created', 'Account Created'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    description = models.TextField()
    details = models.JSONField(default=dict)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.get_risk_level_display()}"

class APIToken(models.Model):
    """API tokens for secure API access"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    token = models.CharField(max_length=64, unique=True)
    permissions = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
    def is_expired(self):
        """Check if token has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def generate_token(self):
        """Generate a new secure token"""
        import secrets
        self.token = secrets.token_urlsafe(48)

class PasswordHistory(models.Model):
    """Track password history to prevent reuse"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
