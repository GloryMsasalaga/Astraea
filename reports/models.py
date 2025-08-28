from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def report_upload_path(instance, filename):
    """Generate upload path for generated reports"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('reports', filename)


class ReportTemplate(models.Model):
    """Model for report templates"""
    
    TEMPLATE_TYPES = [
        ('audit_summary', 'Audit Summary Report'),
        ('reconciliation_report', 'Reconciliation Report'),
        ('financial_overview', 'Financial Overview'),
        ('cash_flow', 'Cash Flow Report'),
        ('expense_analysis', 'Expense Analysis'),
        ('compliance_report', 'Compliance Report'),
        ('custom', 'Custom Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    description = models.TextField(blank=True, null=True)
    
    # Template configuration
    template_config = models.JSONField(default=dict, help_text="JSON configuration for report template")
    
    # Chart configurations
    include_charts = models.BooleanField(default=True)
    chart_types = models.JSONField(default=list, help_text="List of chart types to include")
    
    # Content sections
    include_summary = models.BooleanField(default=True)
    include_detailed_data = models.BooleanField(default=True)
    include_exceptions = models.BooleanField(default=True)
    include_recommendations = models.BooleanField(default=False)
    
    # Styling
    header_color = models.CharField(max_length=7, default='#2E86AB', help_text="Hex color code")
    font_family = models.CharField(max_length=100, default='Arial')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['template_type']),
            models.Index(fields=['is_public', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class GeneratedReport(models.Model):
    """Model for generated reports"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('html', 'HTML'),
        ('excel', 'Excel'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='generated_reports')
    
    # Report metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Generated file
    file = models.FileField(upload_to=report_upload_path, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True, help_text="File size in bytes")
    
    # Report parameters
    date_from = models.DateField()
    date_to = models.DateField()
    filters = models.JSONField(default=dict, help_text="Applied filters for report generation")
    
    # Data sources
    included_documents = models.JSONField(default=list, help_text="List of document IDs included")
    included_reconciliations = models.JSONField(default=list, help_text="List of reconciliation session IDs")
    
    # Generation tracking
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    task_id = models.CharField(max_length=255, blank=True, null=True, help_text="Celery task ID")
    progress_percentage = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    
    # Statistics
    total_pages = models.IntegerField(blank=True, null=True)
    total_charts = models.IntegerField(default=0)
    total_tables = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Access control
    is_public = models.BooleanField(default=False)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['generated_by', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['template', 'created_at']),
            models.Index(fields=['date_from', 'date_to']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def is_expired(self):
        """Check if the report has expired"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False


class ReportSection(models.Model):
    """Model for individual sections within a report"""
    
    SECTION_TYPES = [
        ('header', 'Header'),
        ('summary', 'Summary'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('text', 'Text'),
        ('recommendations', 'Recommendations'),
        ('footer', 'Footer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(GeneratedReport, on_delete=models.CASCADE, related_name='sections')
    
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    title = models.CharField(max_length=255, blank=True, null=True)
    content = models.JSONField(help_text="Section content data")
    
    # Positioning
    order = models.IntegerField(default=0)
    page_number = models.IntegerField(default=1)
    
    # Styling
    style_config = models.JSONField(default=dict, help_text="Section-specific styling")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['report', 'order']
        indexes = [
            models.Index(fields=['report', 'order']),
            models.Index(fields=['section_type']),
        ]
    
    def __str__(self):
        return f"{self.report.title} - {self.get_section_type_display()} ({self.order})"


class ReportChart(models.Model):
    """Model for charts within reports"""
    
    CHART_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('donut', 'Donut Chart'),
        ('gauge', 'Gauge Chart'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(ReportSection, on_delete=models.CASCADE, related_name='charts')
    
    chart_type = models.CharField(max_length=20, choices=CHART_TYPES)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    
    # Chart data
    data = models.JSONField(help_text="Chart data in JSON format")
    chart_config = models.JSONField(default=dict, help_text="Chart configuration options")
    
    # Dimensions
    width = models.IntegerField(default=600)
    height = models.IntegerField(default=400)
    
    # Generated chart file
    chart_image = models.FileField(upload_to='reports/charts/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['section', 'id']
    
    def __str__(self):
        return f"{self.title} - {self.get_chart_type_display()}"


class ReportDownload(models.Model):
    """Model to track report downloads"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(GeneratedReport, on_delete=models.CASCADE, related_name='downloads')
    downloaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Download metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    downloaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['report', 'downloaded_at']),
            models.Index(fields=['downloaded_by', 'downloaded_at']),
        ]
    
    def __str__(self):
        user = self.downloaded_by.username if self.downloaded_by else 'Anonymous'
        return f"{self.report.title} downloaded by {user}"
