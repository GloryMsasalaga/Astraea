from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import ReportTemplate, GeneratedReport, ReportDownload
from .serializers import (
    ReportTemplateSerializer, GeneratedReportSerializer, 
    ReportGenerationRequestSerializer, ReportDownloadSerializer
)
from .tasks import generate_report
import os


class ReportTemplateListView(generics.ListAPIView):
    """List all available report templates"""
    serializer_class = ReportTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReportTemplate.objects.filter(is_active=True).order_by('name')


class ReportTemplateDetailView(generics.RetrieveAPIView):
    """Get details of a specific report template"""
    serializer_class = ReportTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReportTemplate.objects.filter(is_active=True)


class GenerateReportView(APIView):
    """Generate a new report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ReportGenerationRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # Get the template
                    template = get_object_or_404(
                        ReportTemplate,
                        id=serializer.validated_data['template_id'],
                        is_active=True
                    )
                    
                    # Create report record
                    report = GeneratedReport.objects.create(
                        user=request.user,
                        template=template,
                        title=serializer.validated_data['title'],
                        parameters=serializer.validated_data.get('parameters', {}),
                        format=serializer.validated_data.get('format', 'pdf'),
                        status='pending'
                    )
                    
                    # Start report generation asynchronously
                    generate_report.delay(report.id)
                    
                    return Response({
                        'report': GeneratedReportSerializer(report).data,
                        'message': 'Report generation started successfully'
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({
                    'error': f'Error starting report generation: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GeneratedReportListView(generics.ListAPIView):
    """List all generated reports for the authenticated user"""
    serializer_class = GeneratedReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return GeneratedReport.objects.filter(
            generated_by=self.request.user
        ).order_by('-created_at')


class GeneratedReportDetailView(generics.RetrieveAPIView):
    """Get details of a specific generated report"""
    serializer_class = GeneratedReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return GeneratedReport.objects.filter(generated_by=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def report_status(request, report_id):
    """Get the current status of a report generation"""
    try:
        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        return Response({
            'report': GeneratedReportSerializer(report).data,
            'status': report.status,
            'progress': report.progress,
            'error_message': report.error_message
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving report status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def download_report(request, report_id):
    """Download a generated report"""
    try:
        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        if report.status != 'completed' or not report.file_path:
            return Response({
                'error': 'Report is not ready for download'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if file exists
        if not os.path.exists(report.file_path):
            return Response({
                'error': 'Report file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Record download
        ReportDownload.objects.create(
            report=report,
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Serve file
        with open(report.file_path, 'rb') as f:
            content = f.read()
        
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report.title}.pdf"'
        response['Content-Length'] = len(content)
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'Error downloading report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def preview_report(request, report_id):
    """Preview a generated report in browser"""
    try:
        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        if report.status != 'completed' or not report.file_path:
            return Response({
                'error': 'Report is not ready for preview'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if file exists
        if not os.path.exists(report.file_path):
            return Response({
                'error': 'Report file not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Serve file for preview
        with open(report.file_path, 'rb') as f:
            content = f.read()
        
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{report.title}.pdf"'
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'Error previewing report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_report(request, report_id):
    """Delete a generated report"""
    try:
        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        # Delete file if exists
        if report.file_path and os.path.exists(report.file_path):
            try:
                os.remove(report.file_path)
            except OSError:
                pass  # File already deleted or permission issue
        
        # Delete database record
        report.delete()
        
        return Response({
            'message': 'Report deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error deleting report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def regenerate_report(request, report_id):
    """Regenerate an existing report"""
    try:
        old_report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        with transaction.atomic():
            # Create new report record with same parameters
            new_report = GeneratedReport.objects.create(
                user=request.user,
                template=old_report.template,
                title=f"{old_report.title} (Regenerated)",
                parameters=old_report.parameters,
                format=old_report.format,
                status='pending'
            )
            
            # Start report generation asynchronously
            generate_report.delay(new_report.id)
            
            return Response({
                'report': GeneratedReportSerializer(new_report).data,
                'message': 'Report regeneration started successfully'
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({
            'error': f'Error regenerating report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def report_download_history(request, report_id):
    """Get download history for a report"""
    try:
        report = get_object_or_404(
            GeneratedReport,
            id=report_id,
            user=request.user
        )
        
        downloads = ReportDownload.objects.filter(
            report=report
        ).order_by('-downloaded_at')
        
        download_data = []
        for download in downloads:
            download_data.append({
                'id': download.id,
                'downloaded_at': download.downloaded_at,
                'ip_address': download.ip_address,
                'user_agent': download.user_agent
            })
        
        return Response({
            'report_id': report.id,
            'report_title': report.title,
            'download_count': downloads.count(),
            'downloads': download_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving download history: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def template_parameters_schema(request, template_id):
    """Get the parameters schema for a report template"""
    try:
        template = get_object_or_404(
            ReportTemplate,
            id=template_id,
            is_active=True
        )
        
        return Response({
            'template_id': str(template.id),
            'template_name': template.name,
            'parameters_schema': template.parameters_schema or {},
            'description': template.description
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error retrieving template schema: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def report_analytics(request):
    """Get report generation and download analytics"""
    try:
        user = request.user
        
        # Get basic statistics
        total_reports = GeneratedReport.objects.filter(user=user).count()
        completed_reports = GeneratedReport.objects.filter(user=user, status='completed').count()
        failed_reports = GeneratedReport.objects.filter(user=user, status='failed').count()
        total_downloads = ReportDownload.objects.filter(report__user=user).count()
        
        # Template usage
        from django.db.models import Count
        template_usage = GeneratedReport.objects.filter(user=user).values(
            'template__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Format usage
        format_usage = GeneratedReport.objects.filter(user=user).values(
            'format'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent activity
        recent_reports = GeneratedReport.objects.filter(user=user).order_by('-created_at')[:10]
        recent_downloads = ReportDownload.objects.filter(report__user=user).order_by('-downloaded_at')[:10]
        
        return Response({
            'summary': {
                'total_reports': total_reports,
                'completed_reports': completed_reports,
                'failed_reports': failed_reports,
                'success_rate': (completed_reports / total_reports * 100) if total_reports > 0 else 0,
                'total_downloads': total_downloads,
                'avg_downloads_per_report': (total_downloads / completed_reports) if completed_reports > 0 else 0
            },
            'template_usage': list(template_usage),
            'format_usage': list(format_usage),
            'recent_reports': GeneratedReportSerializer(recent_reports, many=True).data,
            'recent_downloads': ReportDownloadSerializer(recent_downloads, many=True).data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error generating analytics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportDownloadListView(generics.ListAPIView):
    """List report downloads for analytics"""
    serializer_class = ReportDownloadSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ReportDownload.objects.filter(
            report__user=self.request.user
        ).select_related('report').order_by('-downloaded_at')
