from django.http import JsonResponse
from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from documents.models import Document
from reconciliation.models import ReconciliationSession
from .models import FinancialMetric, CashflowEntry


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        "status": "healthy",
        "timestamp": "2025-08-20T12:00:00Z"
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financial_metrics_summary(request):
    """Get financial metrics summary for the dashboard"""
    
    # Document statistics
    total_documents = Document.objects.count()
    processed_documents = Document.objects.filter(status='completed').count()
    processing_documents = Document.objects.filter(status='processing').count()
    
    # Reconciliation statistics
    total_reconciliations = ReconciliationSession.objects.count()
    completed_reconciliations = ReconciliationSession.objects.filter(status='completed').count()
    
    # Financial metrics
    revenue = CashflowEntry.objects.filter(
        transaction_type='inflow'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    expenses = CashflowEntry.objects.filter(
        transaction_type='outflow'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    return JsonResponse({
        "documents": {
            "total": total_documents,
            "processed": processed_documents,
            "processing": processing_documents,
            "success_rate": (processed_documents / max(total_documents, 1)) * 100
        },
        "reconciliations": {
            "total": total_reconciliations,
            "completed": completed_reconciliations,
            "completion_rate": (completed_reconciliations / max(total_reconciliations, 1)) * 100
        },
        "financials": {
            "total_revenue": float(revenue),
            "total_expenses": float(expenses),
            "net_profit": float(revenue - expenses)
        }
    })
