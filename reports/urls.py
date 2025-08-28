from django.urls import path

app_name = 'reports'
from . import views

urlpatterns = [
    # Templates
    path('templates/', views.ReportTemplateListView.as_view(), name='template-list'),
    path('templates/<uuid:pk>/', views.ReportTemplateDetailView.as_view(), name='template-detail'),
    path('templates/<uuid:template_id>/schema/', views.template_parameters_schema, name='template-schema'),
    
    # Report generation
    path('generate/', views.GenerateReportView.as_view(), name='generate-report'),
    path('generated/', views.GeneratedReportListView.as_view(), name='generated-list'),
    path('generated/<uuid:pk>/', views.GeneratedReportDetailView.as_view(), name='generated-detail'),
    
    # Report status and actions
    path('status/<uuid:report_id>/', views.report_status, name='report-status'),
    path('download/<uuid:report_id>/', views.download_report, name='download-report'),
    path('preview/<uuid:report_id>/', views.preview_report, name='preview-report'),
    path('delete/<uuid:report_id>/', views.delete_report, name='delete-report'),
    path('regenerate/<uuid:report_id>/', views.regenerate_report, name='regenerate-report'),
    
    # Analytics
    path('analytics/', views.report_analytics, name='report-analytics'),
    path('downloads/', views.ReportDownloadListView.as_view(), name='download-list'),
]
