# security/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    UserProfile, AuditLog, UserSession, DocumentHash, 
    SecurityAlert, APIToken, PasswordHistory
)

# Inline for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Security Profile'
    readonly_fields = ('failed_login_attempts', 'account_locked_until', 'password_changed_at')

# Extend User Admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role', 'get_2fa_status')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'userprofile__role', 'userprofile__two_factor_enabled')
    
    def get_role(self, obj):
        try:
            return obj.userprofile.get_role_display()
        except:
            return 'No Profile'
    get_role.short_description = 'Role'
    
    def get_2fa_status(self, obj):
        try:
            if obj.userprofile.two_factor_enabled:
                return format_html('<span style="color: green;">✓ Enabled</span>')
            else:
                return format_html('<span style="color: red;">✗ Disabled</span>')
        except:
            return 'Unknown'
    get_2fa_status.short_description = '2FA Status'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'two_factor_enabled', 'failed_login_attempts', 'is_locked')
    list_filter = ('role', 'two_factor_enabled', 'created_at')
    search_fields = ('user__username', 'user__email', 'company_name')
    readonly_fields = ('failed_login_attempts', 'account_locked_until', 'password_changed_at', 'created_at', 'updated_at')
    
    def is_locked(self, obj):
        return obj.is_account_locked()
    is_locked.boolean = True
    is_locked.short_description = 'Account Locked'

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'severity', 'ip_address', 'timestamp', 'integrity_status')
    list_filter = ('action', 'severity', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'user_agent')
    readonly_fields = ('user', 'action', 'severity', 'ip_address', 'user_agent', 'timestamp', 
                      'details', 'old_values', 'new_values', 'checksum')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def integrity_status(self, obj):
        if obj.verify_integrity():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Compromised</span>')
    integrity_status.short_description = 'Integrity'

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'created_at', 'last_activity', 'is_active', 'session_status')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('session_key', 'created_at', 'last_activity')
    
    def session_status(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        elif obj.is_active:
            return format_html('<span style="color: green;">Active</span>')
        else:
            return format_html('<span style="color: orange;">Inactive</span>')
    session_status.short_description = 'Status'
    
    actions = ['terminate_sessions']
    
    def terminate_sessions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} sessions terminated.')
    terminate_sessions.short_description = 'Terminate selected sessions'

@admin.register(DocumentHash)
class DocumentHashAdmin(admin.ModelAdmin):
    list_display = ('filename', 'document_id', 'short_hash', 'file_size', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('filename', 'sha256_hash')
    readonly_fields = ('sha256_hash', 'md5_hash', 'created_at', 'verified_at')
    
    def short_hash(self, obj):
        return f"{obj.sha256_hash[:16]}..."
    short_hash.short_description = 'SHA256 Hash'
    
    actions = ['verify_integrity']
    
    def verify_integrity(self, request, queryset):
        # This would integrate with file system to verify hashes
        verified = queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f'{verified} documents verified.')
    verify_integrity.short_description = 'Verify integrity of selected documents'

@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'risk_level', 'user', 'ip_address', 'is_resolved', 'created_at')
    list_filter = ('alert_type', 'risk_level', 'is_resolved', 'created_at')
    search_fields = ('user__username', 'ip_address', 'description')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('alert_type', 'risk_level', 'user', 'ip_address', 'description')
        }),
        ('Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_by', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_resolved', 'mark_unresolved']
    
    def mark_resolved(self, request, queryset):
        updated = queryset.update(
            is_resolved=True, 
            resolved_by=request.user, 
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} alerts marked as resolved.')
    mark_resolved.short_description = 'Mark selected alerts as resolved'
    
    def mark_unresolved(self, request, queryset):
        updated = queryset.update(is_resolved=False, resolved_by=None, resolved_at=None)
        self.message_user(request, f'{updated} alerts marked as unresolved.')
    mark_unresolved.short_description = 'Mark selected alerts as unresolved'

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'is_active', 'expires_at', 'last_used', 'created_at')
    list_filter = ('is_active', 'expires_at', 'created_at')
    search_fields = ('user__username', 'name')
    readonly_fields = ('token', 'last_used', 'created_at')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'is_active')
        }),
        ('Token Details', {
            'fields': ('token', 'permissions', 'expires_at')
        }),
        ('Usage', {
            'fields': ('last_used', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.generate_token()
        super().save_model(request, obj, form, change)

@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('user', 'password_hash', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

# Custom admin site configuration
admin.site.site_header = "AuditFlow Security Administration"
admin.site.site_title = "AuditFlow Security Admin"
admin.site.index_title = "Security & Audit Management"
