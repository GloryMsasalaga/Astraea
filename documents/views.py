from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Document, ExtractedField, ProcessingJob
from .serializers import (
    DocumentSerializer, 
    ExtractedFieldSerializer, 
    ProcessingJobSerializer,
    DocumentUploadSerializer,
    FieldValidationSerializer
)
from .tasks import process_document_ocr
import logging

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for documents"""
    
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter documents by current user"""
        return Document.objects.filter(uploaded_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Start OCR processing for a document"""
        document = self.get_object()
        
        if document.status == 'processing':
            return Response(
                {"error": "Document is already being processed"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start OCR task
        task = process_document_ocr.delay(str(document.id))
        
        # Create processing job record
        job = ProcessingJob.objects.create(
            document=document,
            job_type='ocr',
            task_id=task.id
        )
        
        document.status = 'processing'
        document.save()
        
        return Response({
            "message": "OCR processing started",
            "task_id": task.id,
            "job_id": str(job.id)
        })
    
    @action(detail=True, methods=['get'])
    def processing_status(self, request, pk=None):
        """Get processing status for a document"""
        document = self.get_object()
        
        jobs = document.processing_jobs.order_by('-created_at')
        if jobs.exists():
            latest_job = jobs.first()
            return Response({
                "status": document.status,
                "job_status": latest_job.status,
                "progress": latest_job.progress_percentage,
                "error_message": latest_job.error_message
            })
        
        return Response({"status": document.status})


class ExtractedFieldViewSet(viewsets.ModelViewSet):
    """ViewSet for extracted fields"""
    
    queryset = ExtractedField.objects.all()
    serializer_class = ExtractedFieldSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter fields by current user's documents"""
        return ExtractedField.objects.filter(document__uploaded_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Validate an extracted field"""
        field = self.get_object()
        serializer = FieldValidationSerializer(data=request.data)
        
        if serializer.is_valid():
            field.field_value = serializer.validated_data['field_value']
            field.is_validated = serializer.validated_data['is_valid']
            field.validated_by = request.user
            field.validated_at = timezone.now()
            field.save()
            
            return Response({
                "message": "Field validated successfully",
                "field_id": str(field.id)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProcessingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for processing jobs"""
    
    queryset = ProcessingJob.objects.all()
    serializer_class = ProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter jobs by current user's documents"""
        return ProcessingJob.objects.filter(document__uploaded_by=self.request.user)


class DocumentUploadView(APIView):
    """API view for uploading documents"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """List all uploaded documents for the user"""
        documents = Document.objects.filter(uploaded_by=request.user)
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Upload a new document"""
        serializer = DocumentUploadSerializer(data=request.data)
        if serializer.is_valid():
            document = Document.objects.create(
                uploaded_by=request.user,
                file=serializer.validated_data['file'],
                original_filename=serializer.validated_data['file'].name,
                document_type=serializer.validated_data['document_type']
            )
            document_serializer = DocumentSerializer(document)
            return Response({
                "message": "Document uploaded successfully",
                "document": document_serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Update an uploaded document's metadata (document_type)"""
        document_id = request.data.get('id')
        try:
            document = Document.objects.get(id=document_id, uploaded_by=request.user)
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = DocumentUploadSerializer(document, data=request.data, partial=True)
        if serializer.is_valid():
            document.document_type = serializer.validated_data.get('document_type', document.document_type)
            document.save()
            return Response({"message": "Document updated successfully", "document": DocumentSerializer(document).data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Delete an uploaded document"""
        document_id = request.data.get('id')
        try:
            document = Document.objects.get(id=document_id, uploaded_by=request.user)
            document.delete()
            return Response({"message": "Document deleted successfully"})
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)


class ProcessDocumentView(APIView):
    """API view for starting document processing"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, document_id):
        """Start processing for a specific document"""
        try:
            document = Document.objects.get(
                id=document_id, 
                uploaded_by=request.user
            )
            
            if document.status == 'processing':
                return Response(
                    {"error": "Document is already being processed"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Start OCR task
            task = process_document_ocr.delay(str(document.id))
            
            document.status = 'processing'
            document.save()
            
            return Response({
                "message": "Document processing started",
                "task_id": task.id,
                "document_id": str(document.id)
            })
            
        except Document.DoesNotExist:
            return Response(
                {"error": "Document not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )


class ValidateFieldView(APIView):
    """API view for validating extracted fields"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, field_id):
        """Validate a specific extracted field"""
        try:
            field = ExtractedField.objects.get(
                id=field_id,
                document__uploaded_by=request.user
            )
            
            serializer = FieldValidationSerializer(data=request.data)
            
            if serializer.is_valid():
                field.field_value = serializer.validated_data['field_value']
                field.is_validated = serializer.validated_data['is_valid']
                field.validated_by = request.user
                field.validated_at = timezone.now()
                field.save()
                
                return Response({
                    "message": "Field validated successfully",
                    "field_id": str(field.id)
                })
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ExtractedField.DoesNotExist:
            return Response(
                {"error": "Field not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
