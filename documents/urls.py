from django.urls import path, include

app_name = 'documents'
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'documents', views.DocumentViewSet)
router.register(r'extracted-fields', views.ExtractedFieldViewSet)
router.register(r'processing-jobs', views.ProcessingJobViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('upload/', views.DocumentUploadView.as_view(), name='document-upload'),
    path('process/<uuid:document_id>/', views.ProcessDocumentView.as_view(), name='process-document'),
    path('validate-field/<uuid:field_id>/', views.ValidateFieldView.as_view(), name='validate-field'),
]
