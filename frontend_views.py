# Frontend Views
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json

from documents.models import Document
from reconciliation.models import Reconciliation
from reports.models import Report


@login_required
def dashboard_view(request):
    """Main dashboard view with real data"""
    
    # Get date range for charts (last 6 months)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=180)
    
    # Calculate key metrics
    total_documents = Document.objects.filter(user=request.user).count()
    processed_documents = Document.objects.filter(
        user=request.user, 
        status='completed'
    ).count()
    pending_documents = Document.objects.filter(
        user=request.user, 
        status__in=['pending', 'processing']
    ).count()
    
    # Calculate total amount from processed documents
    total_amount = Document.objects.filter(
        user=request.user,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get recent documents
    recent_documents = Document.objects.filter(
        user=request.user
    ).order_by('-uploaded_at')[:10]
    
    # Chart data for last 6 months
    chart_labels = []
    chart_data = []
    status_data = [processed_documents, pending_documents, 0, 0]  # [completed, processing, pending, failed]
    
    # Generate monthly data
    current_date = start_date
    while current_date <= end_date:
        month_start = current_date.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_count = Document.objects.filter(
            user=request.user,
            uploaded_at__gte=month_start,
            uploaded_at__lt=next_month
        ).count()
        
        chart_labels.append(current_date.strftime('%b %Y'))
        chart_data.append(month_count)
        
        current_date = next_month
    
    # System alerts (example)
    alerts = []
    if pending_documents > 10:
        alerts.append({
            'type': 'warning',
            'title': 'High Pending Volume',
            'message': f'You have {pending_documents} documents pending review.'
        })
    
    context = {
        'total_documents': total_documents,
        'processed_documents': processed_documents,
        'pending_documents': pending_documents,
        'total_amount': total_amount,
        'recent_documents': recent_documents,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'status_data': json.dumps(status_data),
        'alerts': alerts,
    }
    
    return render(request, 'dashboard.html', context)


class CustomLoginView(auth_views.LoginView):
    """Custom login view with enhanced functionality"""
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Handle successful login"""
        messages.success(
            self.request, 
            f'Welcome back, {form.get_user().get_full_name() or form.get_user().username}!'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Handle failed login"""
        messages.error(
            self.request,
            'Invalid username or password. Please try again.'
        )
        return super().form_invalid(form)


@login_required
def upload_documents_view(request):
    """Document upload view with processing"""
    
    if request.method == 'POST':
        try:
            files = request.FILES.getlist('documents')
            document_type = request.POST.get('document_type')
            description = request.POST.get('description', '')
            priority = request.POST.get('priority', 'normal')
            enable_ocr = request.POST.get('enable_ocr') == 'on'
            auto_process = request.POST.get('auto_process') == 'on'
            action = request.POST.get('action', 'upload_process')
            
            if not files:
                messages.error(request, 'Please select at least one file to upload.')
                return render(request, 'documents/upload.html')
            
            # Process each file
            uploaded_count = 0
            for file in files:
                # Validate file size and type
                if file.size > 10 * 1024 * 1024:  # 10MB limit
                    messages.warning(request, f'File {file.name} is too large (max 10MB)')
                    continue
                
                # Create document record
                document = Document.objects.create(
                    user=request.user,
                    name=file.name,
                    file=file,
                    document_type=document_type,
                    description=description,
                    priority=priority,
                    status='processing' if auto_process else 'pending'
                )
                
                uploaded_count += 1
                
                # Queue OCR processing if enabled
                if enable_ocr and auto_process:
                    from documents.tasks import process_document_ocr
                    process_document_ocr.delay(document.id)
            
            if uploaded_count > 0:
                messages.success(
                    request, 
                    f'Successfully uploaded {uploaded_count} document(s). '
                    f'{"Processing started automatically." if auto_process else "Ready for manual processing."}'
                )
                
                if action == 'save_draft':
                    return render(request, 'documents/upload.html')
                else:
                    return redirect('documents:list')
            else:
                messages.error(request, 'No files were successfully uploaded.')
        
        except Exception as e:
            messages.error(request, f'Upload failed: {str(e)}')
    
    return render(request, 'documents/upload.html')


@login_required
def documents_list_view(request):
    """List all documents for the user"""
    
    documents = Document.objects.filter(
        user=request.user
    ).order_by('-uploaded_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        documents = documents.filter(status=status_filter)
    
    # Filter by document type if provided
    type_filter = request.GET.get('type')
    if type_filter:
        documents = documents.filter(document_type=type_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        documents = documents.filter(
            name__icontains=search_query
        )
    
    context = {
        'documents': documents,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_query': search_query,
    }
    
    return render(request, 'documents/list.html', context)


@login_required
def document_detail_view(request, pk):
    """View individual document details"""
    
    try:
        document = Document.objects.get(pk=pk, user=request.user)
    except Document.DoesNotExist:
        messages.error(request, 'Document not found.')
        return redirect('documents:list')
    
    context = {
        'document': document,
    }
    
    return render(request, 'documents/detail.html', context)


@login_required
def reconciliation_list_view(request):
    """List reconciliation records"""
    
    reconciliations = Reconciliation.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    context = {
        'reconciliations': reconciliations,
    }
    
    return render(request, 'reconciliation/list.html', context)


@login_required
def reports_list_view(request):
    """List generated reports"""
    
    reports = Report.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    context = {
        'reports': reports,
    }
    
    return render(request, 'reports/list.html', context)
