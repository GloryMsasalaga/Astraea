# Frontend URL Configuration
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Dashboard
    path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    
    # Document Management (placeholder URLs)
    path('documents/', include([
        path('', TemplateView.as_view(template_name='documents/list.html'), name='list'),
        path('upload/', TemplateView.as_view(template_name='documents/upload.html'), name='upload'),
        path('<int:pk>/', TemplateView.as_view(template_name='documents/detail.html'), name='detail'),
    ]), {'namespace': 'documents'}),
    
    # Transactions
    path('transactions/', include([
        path('', TemplateView.as_view(template_name='transactions/list.html'), name='list'),
        path('create/', TemplateView.as_view(template_name='transactions/create.html'), name='create'),
    ]), {'namespace': 'transactions'}),
    
    # Reconciliation (placeholder URLs)
    path('reconciliation/', include([
        path('', TemplateView.as_view(template_name='reconciliation/list.html'), name='list'),
        path('create/', TemplateView.as_view(template_name='reconciliation/create.html'), name='create'),
    ]), {'namespace': 'reconciliation'}),
    
    # Reports (placeholder URLs)
    path('reports/', include([
        path('', TemplateView.as_view(template_name='reports/list.html'), name='list'),
        path('generate/', TemplateView.as_view(template_name='reports/generate.html'), name='generate'),
    ]), {'namespace': 'reports'}),
    
    # Settings
    path('settings/', TemplateView.as_view(template_name='settings.html'), name='settings'),
]
