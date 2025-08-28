from django.contrib import admin
from .models import Document, ExtractedField, ProcessingJob


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin interface for documents"""
    
    list_display = ('original_filename', 'document_type', 'uploaded_by', 'status', 'created_at')
    list_filter = ('document_type', 'status', 'created_at')
    search_fields = ('original_filename', 'uploaded_by__username')
    readonly_fields = ('id', 'file_size', 'file_extension', 'created_at', 'updated_at', 'processed_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'uploaded_by', 'file', 'original_filename', 'document_type', 'status')
        }),
        ('OCR Results', {
            'fields': ('ocr_text', 'confidence_score'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExtractedField)
class ExtractedFieldAdmin(admin.ModelAdmin):
    """Admin interface for extracted fields"""
    
    list_display = ('document', 'field_type', 'field_name', 'field_value', 'confidence_score', 'is_validated')
    list_filter = ('field_type', 'is_validated', 'created_at')
    search_fields = ('field_name', 'field_value', 'document__original_filename')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'document', 'field_type', 'field_name', 'field_value', 'confidence_score')
        }),
        ('Position (for images)', {
            'fields': ('x_coordinate', 'y_coordinate', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('is_validated', 'validated_by', 'validated_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    """Admin interface for processing jobs"""
    
    list_display = ('document', 'job_type', 'status', 'progress_percentage', 'created_at')
    list_filter = ('job_type', 'status', 'created_at')
    search_fields = ('document__original_filename', 'task_id')
    readonly_fields = ('id', 'created_at', 'started_at', 'completed_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'document', 'job_type', 'status', 'task_id')
        }),
        ('Progress', {
            'fields': ('progress_percentage', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
