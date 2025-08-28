from django.urls import path

app_name = 'reconciliation'
from . import views

urlpatterns = [
    # File upload and session management
    path('upload-files/', views.FileUploadView.as_view(), name='upload-files'),
    path('sessions/', views.ReconciliationSessionListView.as_view(), name='session-list'),
    path('sessions/<uuid:pk>/', views.ReconciliationSessionDetailView.as_view(), name='session-detail'),
    
    # Reconciliation process
    path('start-reconciliation/<uuid:session_id>/', views.start_reconciliation, name='start-reconciliation'),
    path('sessions/<uuid:session_id>/status/', views.session_status, name='session-status'),
    path('sessions/<uuid:session_id>/summary/', views.reconciliation_summary, name='reconciliation-summary'),
    
    # Records
    path('sessions/<uuid:session_id>/ledger-records/', views.LedgerRecordListView.as_view(), name='ledger-records'),
    path('sessions/<uuid:session_id>/bank-records/', views.BankRecordListView.as_view(), name='bank-records'),
    path('sessions/<uuid:session_id>/matches/', views.TransactionMatchListView.as_view(), name='transaction-matches'),
    path('sessions/<uuid:session_id>/exceptions/', views.ReconciliationExceptionListView.as_view(), name='reconciliation-exceptions'),
    
    # Match and exception management
    path('confirm-match/<uuid:match_id>/', views.confirm_match, name='confirm-match'),
    path('resolve-exception/<uuid:exception_id>/', views.resolve_exception, name='resolve-exception'),
]
