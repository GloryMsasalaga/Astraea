from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def reconciliation_upload_path(instance, filename):
    """Generate upload path for reconciliation files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('reconciliation', filename)


class ReconciliationSession(models.Model):
    """Model for reconciliation sessions"""
    
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reconciliation_sessions')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    
    # Files
    ledger_file = models.FileField(upload_to=reconciliation_upload_path)
    bank_statement_file = models.FileField(upload_to=reconciliation_upload_path)
    
    # Reconciliation settings
    date_tolerance_days = models.IntegerField(default=0, help_text="Days tolerance for date matching")
    amount_tolerance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Amount tolerance for matching")
    
    # Results summary
    total_ledger_records = models.IntegerField(default=0)
    total_bank_records = models.IntegerField(default=0)
    matched_records = models.IntegerField(default=0)
    unmatched_ledger_records = models.IntegerField(default=0)
    unmatched_bank_records = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.status}"
    
    @property
    def match_percentage(self):
        """Calculate matching percentage"""
        if self.total_ledger_records == 0:
            return 0
        return (self.matched_records / self.total_ledger_records) * 100


class LedgerRecord(models.Model):
    """Model for ledger records from uploaded CSV/Excel"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ReconciliationSession, on_delete=models.CASCADE, related_name='ledger_records')
    
    # Standard fields (can be mapped from CSV columns)
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)
    account = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    
    # Raw data from CSV
    raw_data = models.JSONField(help_text="Original row data from CSV/Excel")
    row_number = models.IntegerField(help_text="Row number in original file")
    
    # Matching status
    is_matched = models.BooleanField(default=False)
    match_confidence = models.FloatField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date', 'amount']
        indexes = [
            models.Index(fields=['session', 'date']),
            models.Index(fields=['session', 'is_matched']),
            models.Index(fields=['amount']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.description[:50]} - ${self.amount}"


class BankRecord(models.Model):
    """Model for bank statement records from uploaded CSV/Excel"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ReconciliationSession, on_delete=models.CASCADE, related_name='bank_records')
    
    # Standard fields (can be mapped from CSV columns)
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Raw data from CSV
    raw_data = models.JSONField(help_text="Original row data from CSV/Excel")
    row_number = models.IntegerField(help_text="Row number in original file")
    
    # Matching status
    is_matched = models.BooleanField(default=False)
    match_confidence = models.FloatField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date', 'amount']
        indexes = [
            models.Index(fields=['session', 'date']),
            models.Index(fields=['session', 'is_matched']),
            models.Index(fields=['amount']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.description[:50]} - ${self.amount}"


class TransactionMatch(models.Model):
    """Model for matched transactions between ledger and bank records"""
    
    MATCH_TYPES = [
        ('exact', 'Exact Match'),
        ('partial', 'Partial Match'),
        ('manual', 'Manual Match'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ReconciliationSession, on_delete=models.CASCADE, related_name='matches')
    
    # Related records
    ledger_record = models.ForeignKey(LedgerRecord, on_delete=models.CASCADE, related_name='matches')
    bank_record = models.ForeignKey(BankRecord, on_delete=models.CASCADE, related_name='matches')
    
    # Match details
    match_type = models.CharField(max_length=20, choices=MATCH_TYPES)
    confidence_score = models.FloatField(help_text="Confidence score of the match (0-1)")
    
    # Differences
    date_difference_days = models.IntegerField(default=0)
    amount_difference = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Manual review
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_matches')
    confirmed_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-confidence_score', 'created_at']
        indexes = [
            models.Index(fields=['session', 'confidence_score']),
            models.Index(fields=['match_type']),
            models.Index(fields=['is_confirmed']),
        ]
    
    def __str__(self):
        return f"Match: {self.ledger_record.description[:30]} <-> {self.bank_record.description[:30]} ({self.confidence_score:.2f})"


class ReconciliationException(models.Model):
    """Model for unmatched or problematic records that need manual attention"""
    
    EXCEPTION_TYPES = [
        ('unmatched_ledger', 'Unmatched Ledger Record'),
        ('unmatched_bank', 'Unmatched Bank Record'),
        ('duplicate_match', 'Duplicate Match'),
        ('amount_discrepancy', 'Amount Discrepancy'),
        ('date_discrepancy', 'Date Discrepancy'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ReconciliationSession, on_delete=models.CASCADE, related_name='exceptions')
    
    exception_type = models.CharField(max_length=30, choices=EXCEPTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Related records (nullable for cases where we only have one side)
    ledger_record = models.ForeignKey(LedgerRecord, on_delete=models.CASCADE, null=True, blank=True, related_name='exceptions')
    bank_record = models.ForeignKey(BankRecord, on_delete=models.CASCADE, null=True, blank=True, related_name='exceptions')
    
    # Exception details
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')
    
    # Resolution
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_exceptions')
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['exception_type']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.exception_type} - {self.description[:50]}"
