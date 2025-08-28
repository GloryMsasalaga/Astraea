from django.shortcuts import get_object_or_404
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import (
    ReconciliationSession, LedgerRecord, BankRecord, 
    TransactionMatch, ReconciliationException
)
from .serializers import (
    FileUploadSerializer, ReconciliationSessionSerializer,
    LedgerRecordSerializer, BankRecordSerializer,
    TransactionMatchSerializer, ReconciliationExceptionSerializer
)
from .tasks import process_reconciliation_files, start_reconciliation_matching


class FileUploadView(APIView):
    """Upload reconciliation files (ledger and bank statement)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # Create reconciliation session
                    session = ReconciliationSession.objects.create(
                        user=request.user,
                        name=serializer.validated_data['name'],
                        ledger_file=serializer.validated_data['ledger_file'],
                        bank_statement_file=serializer.validated_data['bank_statement_file'],
                        date_tolerance_days=serializer.validated_data.get('date_tolerance_days', 3),
                        amount_tolerance=serializer.validated_data.get('amount_tolerance', 0.01),
                        status='uploaded'
                    )
                    
                    # Start file processing asynchronously
                    process_reconciliation_files.delay(session.id)
                    
                    return Response({
                        'session': ReconciliationSessionSerializer(session).data,
                        'message': 'Files uploaded successfully. Processing started.'
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({
                    'error': f'Error processing files: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReconciliationSessionListView(generics.ListAPIView):
    """List all reconciliation sessions for the authenticated user"""
    serializer_class = ReconciliationSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReconciliationSession.objects.filter(
            created_by=self.request.user
        ).order_by('-created_at')


class ReconciliationSessionDetailView(generics.RetrieveAPIView):
    """Get details of a specific reconciliation session"""
    serializer_class = ReconciliationSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReconciliationSession.objects.filter(created_by=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def start_reconciliation(request, session_id):
    """Start the reconciliation matching process"""
    try:
        session = get_object_or_404(
            ReconciliationSession, 
            id=session_id, 
            user=request.user
        )
        
        if session.status != 'processed':
            return Response({
                'error': 'Session files must be processed before starting reconciliation'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start reconciliation matching asynchronously
        start_reconciliation_matching.delay(session.id)
        
        session.status = 'reconciling'
        session.save()
        
        return Response({
            'message': 'Reconciliation started successfully',
            'session_id': session.id
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error starting reconciliation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def session_status(request, session_id):
    """Get the current status of a reconciliation session"""
    try:
        session = get_object_or_404(
            ReconciliationSession, 
            id=session_id, 
            user=request.user
        )
        
        # Get summary statistics
        total_ledger = LedgerRecord.objects.filter(session=session).count()
        total_bank = BankRecord.objects.filter(session=session).count()
        total_matches = TransactionMatch.objects.filter(
            ledger_record__session=session,
            is_confirmed=True
        ).count()
        total_exceptions = ReconciliationException.objects.filter(
            session=session
        ).count()
        
        return Response({
            'session': ReconciliationSessionSerializer(session).data,
            'statistics': {
                'total_ledger_records': total_ledger,
                'total_bank_records': total_bank,
                'total_matches': total_matches,
                'total_exceptions': total_exceptions,
                'match_rate': (total_matches / max(total_ledger, 1)) * 100
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving session status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LedgerRecordListView(generics.ListAPIView):
    """List ledger records for a session"""
    serializer_class = LedgerRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        session_id = self.kwargs['session_id']
        return LedgerRecord.objects.filter(
            session_id=session_id,
            session__user=self.request.user
        ).order_by('date')


class BankRecordListView(generics.ListAPIView):
    """List bank records for a session"""
    serializer_class = BankRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        session_id = self.kwargs['session_id']
        return BankRecord.objects.filter(
            session_id=session_id,
            session__user=self.request.user
        ).order_by('date')


class TransactionMatchListView(generics.ListAPIView):
    """List transaction matches for a session"""
    serializer_class = TransactionMatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        session_id = self.kwargs['session_id']
        return TransactionMatch.objects.filter(
            ledger_record__session_id=session_id,
            ledger_record__session__user=self.request.user
        ).order_by('-confidence_score')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_match(request, match_id):
    """Confirm a transaction match"""
    try:
        match = get_object_or_404(
            TransactionMatch,
            id=match_id,
            ledger_record__session__user=request.user
        )
        
        with transaction.atomic():
            # Confirm the match
            match.is_confirmed = True
            match.save()
            
            # Mark records as matched
            match.ledger_record.is_matched = True
            match.ledger_record.save()
            
            match.bank_record.is_matched = True
            match.bank_record.save()
            
            # Remove any related exceptions
            ReconciliationException.objects.filter(
                session=match.ledger_record.session,
                record_type='ledger',
                record_id=match.ledger_record.id
            ).delete()
            
            ReconciliationException.objects.filter(
                session=match.ledger_record.session,
                record_type='bank',
                record_id=match.bank_record.id
            ).delete()
        
        return Response({
            'message': 'Match confirmed successfully',
            'match': TransactionMatchSerializer(match).data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error confirming match: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReconciliationExceptionListView(generics.ListAPIView):
    """List reconciliation exceptions for a session"""
    serializer_class = ReconciliationExceptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        session_id = self.kwargs['session_id']
        return ReconciliationException.objects.filter(
            session_id=session_id,
            session__user=self.request.user
        ).order_by('-created_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def resolve_exception(request, exception_id):
    """Resolve a reconciliation exception"""
    try:
        exception = get_object_or_404(
            ReconciliationException,
            id=exception_id,
            session__user=request.user
        )
        
        resolution = request.data.get('resolution')
        notes = request.data.get('notes', '')
        
        if not resolution:
            return Response({
                'error': 'Resolution is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            exception.resolution = resolution
            exception.notes = notes
            exception.is_resolved = True
            exception.save()
            
            # If manual match, create the match record
            if resolution == 'manual_match':
                bank_record_id = request.data.get('bank_record_id')
                if bank_record_id:
                    bank_record = get_object_or_404(
                        BankRecord,
                        id=bank_record_id,
                        session=exception.session
                    )
                    
                    # Get the ledger record
                    ledger_record = get_object_or_404(
                        LedgerRecord,
                        id=exception.record_id,
                        session=exception.session
                    )
                    
                    # Create manual match
                    TransactionMatch.objects.create(
                        ledger_record=ledger_record,
                        bank_record=bank_record,
                        match_type='manual',
                        confidence_score=1.0,
                        is_confirmed=True
                    )
                    
                    # Mark records as matched
                    ledger_record.is_matched = True
                    ledger_record.save()
                    
                    bank_record.is_matched = True
                    bank_record.save()
        
        return Response({
            'message': 'Exception resolved successfully',
            'exception': ReconciliationExceptionSerializer(exception).data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error resolving exception: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def reconciliation_summary(request, session_id):
    """Get reconciliation summary for a session"""
    try:
        session = get_object_or_404(
            ReconciliationSession,
            id=session_id,
            user=request.user
        )
        
        # Calculate summary statistics
        total_ledger = LedgerRecord.objects.filter(session=session).count()
        total_bank = BankRecord.objects.filter(session=session).count()
        
        matched_ledger = LedgerRecord.objects.filter(
            session=session,
            is_matched=True
        ).count()
        
        matched_bank = BankRecord.objects.filter(
            session=session,
            is_matched=True
        ).count()
        
        total_matches = TransactionMatch.objects.filter(
            ledger_record__session=session,
            is_confirmed=True
        ).count()
        
        auto_matches = TransactionMatch.objects.filter(
            ledger_record__session=session,
            is_confirmed=True,
            match_type='auto'
        ).count()
        
        manual_matches = TransactionMatch.objects.filter(
            ledger_record__session=session,
            is_confirmed=True,
            match_type='manual'
        ).count()
        
        total_exceptions = ReconciliationException.objects.filter(
            session=session
        ).count()
        
        resolved_exceptions = ReconciliationException.objects.filter(
            session=session,
            is_resolved=True
        ).count()
        
        # Calculate amounts
        from django.db.models import Sum
        
        matched_amount = TransactionMatch.objects.filter(
            ledger_record__session=session,
            is_confirmed=True
        ).aggregate(total=Sum('ledger_record__amount'))['total'] or 0
        
        unmatched_ledger_amount = LedgerRecord.objects.filter(
            session=session,
            is_matched=False
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        unmatched_bank_amount = BankRecord.objects.filter(
            session=session,
            is_matched=False
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'session': ReconciliationSessionSerializer(session).data,
            'summary': {
                'total_records': {
                    'ledger': total_ledger,
                    'bank': total_bank
                },
                'matched_records': {
                    'ledger': matched_ledger,
                    'bank': matched_bank
                },
                'matches': {
                    'total': total_matches,
                    'auto': auto_matches,
                    'manual': manual_matches
                },
                'exceptions': {
                    'total': total_exceptions,
                    'resolved': resolved_exceptions,
                    'pending': total_exceptions - resolved_exceptions
                },
                'match_rates': {
                    'ledger': (matched_ledger / max(total_ledger, 1)) * 100,
                    'bank': (matched_bank / max(total_bank, 1)) * 100
                },
                'amounts': {
                    'matched': float(matched_amount),
                    'unmatched_ledger': float(unmatched_ledger_amount),
                    'unmatched_bank': float(unmatched_bank_amount)
                }
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error generating reconciliation summary: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
