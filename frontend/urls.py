from django.urls import path
from django.shortcuts import redirect
from . import views
from django.contrib.auth import views as auth_views

app_name = 'frontend'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transactions/', views.transactions, name='transactions'),
    path('reconciliation/', views.reconciliation, name='reconciliation'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),
    path('logout/', views.logout_view, name='logout'),
]
