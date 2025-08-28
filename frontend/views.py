from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

def home_view(request):
    """Beautiful homepage for non-authenticated users"""
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    return render(request, 'home.html')

def login_view(request):
    """Custom login view"""
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    return render(request, 'registration/login.html')

def logout_view(request):
    """Logout view"""
    logout(request)
    return redirect('frontend:login')

@login_required
def dashboard(request):
    """Dashboard page"""
    return render(request, 'dashboard.html')

@login_required
def transactions(request):
    """Transactions page"""
    return render(request, 'transactions/list.html')

@login_required
def reconciliation(request):
    """Reconciliation page"""
    return render(request, 'reconciliation/list.html')

@login_required
def reports(request):
    """Reports page"""
    return render(request, 'reports/list.html')

@login_required
def settings(request):
    """Settings page"""
    return render(request, 'settings.html')
