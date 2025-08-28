import graphene
from graphene_django import DjangoObjectType
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import FinancialMetric, CashflowEntry, ExpenseCategory, ExpenseDistribution
from documents.models import Document
from reconciliation.models import ReconciliationSession, TransactionMatch


class FinancialMetricType(DjangoObjectType):
    class Meta:
        model = FinancialMetric
        fields = '__all__'


class CashflowEntryType(DjangoObjectType):
    class Meta:
        model = CashflowEntry
        fields = '__all__'


class ExpenseCategoryType(DjangoObjectType):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseDistributionType(DjangoObjectType):
    class Meta:
        model = ExpenseDistribution
        fields = '__all__'


class CashflowTrendData(graphene.ObjectType):
    """Type for cashflow trend data"""
    date = graphene.Date()
    inflow = graphene.Decimal()
    outflow = graphene.Decimal()
    net_flow = graphene.Decimal()


class FinancialSummary(graphene.ObjectType):
    """Type for financial summary data"""
    total_revenue = graphene.Decimal()
    total_expenses = graphene.Decimal()
    net_profit = graphene.Decimal()
    total_documents = graphene.Int()
    processed_documents = graphene.Int()
    reconciliation_sessions = graphene.Int()


class Query(graphene.ObjectType):
    """GraphQL queries for dashboard data"""
    
    # Financial metrics
    financial_metrics = graphene.List(FinancialMetricType)
    financial_summary = graphene.Field(FinancialSummary)
    
    # Revenue and expenses
    total_revenue = graphene.Decimal(
        period_start=graphene.Date(),
        period_end=graphene.Date()
    )
    total_expenses = graphene.Decimal(
        period_start=graphene.Date(),
        period_end=graphene.Date()
    )
    
    # Cashflow
    cashflow_entries = graphene.List(CashflowEntryType)
    cashflow_trend = graphene.List(
        CashflowTrendData,
        period_start=graphene.Date(),
        period_end=graphene.Date(),
        interval=graphene.String()  # 'daily', 'weekly', 'monthly'
    )
    
    # Expense distribution
    expense_distribution = graphene.List(ExpenseDistributionType)
    expense_categories = graphene.List(ExpenseCategoryType)
    
    def resolve_financial_metrics(self, info):
        """Get all financial metrics"""
        return FinancialMetric.objects.all().order_by('-period_end')
    
    def resolve_financial_summary(self, info):
        """Get financial summary for dashboard"""
        # Calculate current month metrics
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Get revenue and expenses from cashflow entries
        revenue = CashflowEntry.objects.filter(
            date__gte=month_start,
            transaction_type='inflow'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        expenses = CashflowEntry.objects.filter(
            date__gte=month_start,
            transaction_type='outflow'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Document statistics
        total_docs = Document.objects.count()
        processed_docs = Document.objects.filter(status='completed').count()
        
        # Reconciliation statistics
        reconciliation_count = ReconciliationSession.objects.count()
        
        return FinancialSummary(
            total_revenue=revenue,
            total_expenses=expenses,
            net_profit=revenue - expenses,
            total_documents=total_docs,
            processed_documents=processed_docs,
            reconciliation_sessions=reconciliation_count
        )
    
    def resolve_total_revenue(self, info, period_start=None, period_end=None):
        """Get total revenue for a period"""
        queryset = CashflowEntry.objects.filter(transaction_type='inflow')
        
        if period_start:
            queryset = queryset.filter(date__gte=period_start)
        if period_end:
            queryset = queryset.filter(date__lte=period_end)
        
        total = queryset.aggregate(total=Sum('amount'))['total']
        return total or Decimal('0')
    
    def resolve_total_expenses(self, info, period_start=None, period_end=None):
        """Get total expenses for a period"""
        queryset = CashflowEntry.objects.filter(transaction_type='outflow')
        
        if period_start:
            queryset = queryset.filter(date__gte=period_start)
        if period_end:
            queryset = queryset.filter(date__lte=period_end)
        
        total = queryset.aggregate(total=Sum('amount'))['total']
        return total or Decimal('0')
    
    def resolve_cashflow_entries(self, info):
        """Get all cashflow entries"""
        return CashflowEntry.objects.all().order_by('-date')
    
    def resolve_cashflow_trend(self, info, period_start=None, period_end=None, interval='daily'):
        """Get cashflow trend data"""
        if not period_start:
            period_start = timezone.now().date() - timedelta(days=30)
        if not period_end:
            period_end = timezone.now().date()
        
        trend_data = []
        
        if interval == 'daily':
            delta = timedelta(days=1)
        elif interval == 'weekly':
            delta = timedelta(weeks=1)
        elif interval == 'monthly':
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=1)
        
        current_date = period_start
        while current_date <= period_end:
            end_date = current_date + delta - timedelta(days=1)
            if end_date > period_end:
                end_date = period_end
            
            # Calculate inflow and outflow for this period
            inflow = CashflowEntry.objects.filter(
                date__gte=current_date,
                date__lte=end_date,
                transaction_type='inflow'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            outflow = CashflowEntry.objects.filter(
                date__gte=current_date,
                date__lte=end_date,
                transaction_type='outflow'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            trend_data.append(CashflowTrendData(
                date=current_date,
                inflow=inflow,
                outflow=outflow,
                net_flow=inflow - outflow
            ))
            
            current_date += delta
        
        return trend_data
    
    def resolve_expense_distribution(self, info):
        """Get expense distribution data"""
        return ExpenseDistribution.objects.all().order_by('-total_amount')
    
    def resolve_expense_categories(self, info):
        """Get all expense categories"""
        return ExpenseCategory.objects.filter(is_active=True).order_by('name')


schema = graphene.Schema(query=Query)
