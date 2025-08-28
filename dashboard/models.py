from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class FinancialMetric(models.Model):
    """Model for storing calculated financial metrics"""
    
    METRIC_TYPES = [
        ('revenue', 'Total Revenue'),
        ('expenses', 'Total Expenses'),
        ('profit', 'Net Profit'),
        ('cash_flow', 'Cash Flow'),
        ('accounts_receivable', 'Accounts Receivable'),
        ('accounts_payable', 'Accounts Payable'),
        ('tax_liability', 'Tax Liability'),
        ('operating_expense', 'Operating Expenses'),
        ('other', 'Other'),
    ]
    
    PERIOD_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES)
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Metric values
    value = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Metadata
    calculated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    calculation_method = models.TextField(blank=True, help_text="Description of how this metric was calculated")
    data_sources = models.JSONField(default=list, help_text="List of data sources used for calculation")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_end', 'metric_type']
        indexes = [
            models.Index(fields=['metric_type', 'period_type']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['metric_type', 'period_type', 'period_start', 'period_end']
    
    def __str__(self):
        return f"{self.get_metric_type_display()} ({self.period_start} to {self.period_end}): {self.value}"


class CashflowEntry(models.Model):
    """Model for cashflow tracking"""
    
    TRANSACTION_TYPES = [
        ('inflow', 'Cash Inflow'),
        ('outflow', 'Cash Outflow'),
    ]
    
    CATEGORIES = [
        ('operations', 'Operating Activities'),
        ('investing', 'Investing Activities'),
        ('financing', 'Financing Activities'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    reference = models.CharField(max_length=255, blank=True, null=True)
    
    # Source tracking
    source_document_id = models.UUIDField(blank=True, null=True, help_text="Reference to source document")
    source_reconciliation_id = models.UUIDField(blank=True, null=True, help_text="Reference to reconciliation session")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date', 'transaction_type']),
            models.Index(fields=['category']),
            models.Index(fields=['source_document_id']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.get_transaction_type_display()}: {self.amount}"


class ExpenseCategory(models.Model):
    """Model for expense categorization"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    
    # Budget settings
    monthly_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    yearly_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Visual settings
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color code for charts")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']
    
    def __str__(self):
        if self.parent_category:
            return f"{self.parent_category.name} > {self.name}"
        return self.name


class ExpenseDistribution(models.Model):
    """Model for storing expense distribution data for charts"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='distributions')
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Distribution data
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_count = models.IntegerField(default=0)
    percentage_of_total = models.FloatField(help_text="Percentage of total expenses for the period")
    
    # Comparison with budget
    budget_amount = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    budget_variance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end', '-total_amount']
        indexes = [
            models.Index(fields=['category', 'period_start', 'period_end']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        unique_together = ['category', 'period_start', 'period_end']
    
    def __str__(self):
        return f"{self.category.name} ({self.period_start} to {self.period_end}): {self.total_amount}"


class DashboardCache(models.Model):
    """Model for caching dashboard query results"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cache_key = models.CharField(max_length=255, unique=True)
    query_type = models.CharField(max_length=100)
    
    # Cached data
    cached_data = models.JSONField()
    
    # Cache metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Query parameters that generated this cache
    query_parameters = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cache_key']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['query_type']),
        ]
    
    def __str__(self):
        return f"Cache: {self.query_type} - {self.cache_key}"
    
    @property
    def is_expired(self):
        """Check if the cache entry has expired"""
        return timezone.now() > self.expires_at
    
    def refresh_expiry(self, hours=24):
        """Refresh the expiry time"""
        self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        self.save(update_fields=['expires_at'])
