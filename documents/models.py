from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def document_upload_path(instance, filename):
    """Generate upload path for documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('documents', filename)


class Document(models.Model):
    """Model for uploaded documents (invoices, receipts, contracts)"""
    
    DOCUMENT_TYPES = [
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('contract', 'Contract'),
        ('statement', 'Statement'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    
    # OCR Results
    ocr_text = models.TextField(blank=True, null=True)
    confidence_score = models.FloatField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['document_type']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} - {self.document_type}"
    
    @property
    def file_size(self):
        """Get file size in bytes"""
        try:
            return self.file.size
        except:
            return 0
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.original_filename)[1].lower()


class ExtractedField(models.Model):
    """Model for extracted fields from documents"""
    
    FIELD_TYPES = [
        ('date', 'Date'),
        ('amount', 'Amount'),
        ('vendor', 'Vendor'),
        ('description', 'Description'),
        ('invoice_number', 'Invoice Number'),
        ('tax_amount', 'Tax Amount'),
        ('currency', 'Currency'),
        ('payment_terms', 'Payment Terms'),
        ('due_date', 'Due Date'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='extracted_fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    field_name = models.CharField(max_length=100)
    field_value = models.TextField()
    confidence_score = models.FloatField(blank=True, null=True)
    
    # Bounding box coordinates (for image documents)
    x_coordinate = models.IntegerField(blank=True, null=True)
    y_coordinate = models.IntegerField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    
    # Validation
    is_validated = models.BooleanField(default=False)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_fields')
    validated_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['field_type', 'field_name']
        indexes = [
            models.Index(fields=['document', 'field_type']),
            models.Index(fields=['field_type']),
            models.Index(fields=['is_validated']),
        ]
    
    def __str__(self):
        return f"{self.document.original_filename} - {self.field_name}: {self.field_value[:50]}"


class ProcessingJob(models.Model):
    """Model to track OCR processing jobs"""
    
    JOB_TYPES = [
        ('ocr', 'OCR Processing'),
        ('field_extraction', 'Field Extraction'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='processing_jobs')
    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Celery task tracking
    task_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Progress tracking
    progress_percentage = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', 'job_type']),
            models.Index(fields=['status']),
            models.Index(fields=['task_id']),
        ]
    
    def __str__(self):
        return f"{self.document.original_filename} - {self.job_type} ({self.status})"
