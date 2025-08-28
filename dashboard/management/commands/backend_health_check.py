from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.conf import settings
import os
import sys

class Command(BaseCommand):
    help = 'Comprehensive backend health check'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== DJANGO ACCOUNTING SYSTEM HEALTH CHECK ===\n'))
        
        issues = []
        successes = []
        
        # 1. Database Connection Test
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            successes.append("✓ Database connection successful")
        except Exception as e:
            issues.append(f"✗ Database connection failed: {e}")
        
        # 2. Settings Validation
        try:
            from django.core.checks import run_checks
            check_errors = run_checks()
            if not check_errors:
                successes.append("✓ Django configuration valid")
            else:
                for error in check_errors:
                    issues.append(f"✗ Configuration issue: {error}")
        except Exception as e:
            issues.append(f"✗ Settings validation failed: {e}")
        
        # 3. Apps Import Test
        apps_to_test = ['documents', 'reconciliation', 'reports', 'dashboard']
        for app_name in apps_to_test:
            try:
                # Test models
                exec(f"from {app_name}.models import *")
                successes.append(f"✓ {app_name}.models imported successfully")
                
                # Test views
                exec(f"from {app_name}.views import *")
                successes.append(f"✓ {app_name}.views imported successfully")
                
                # Test serializers (if exists)
                try:
                    exec(f"from {app_name}.serializers import *")
                    successes.append(f"✓ {app_name}.serializers imported successfully")
                except ImportError:
                    pass  # Some apps might not have serializers
                    
                # Test tasks (if exists)
                try:
                    exec(f"from {app_name}.tasks import *")
                    successes.append(f"✓ {app_name}.tasks imported successfully")
                except ImportError:
                    pass  # Some apps might not have tasks
                    
            except Exception as e:
                issues.append(f"✗ {app_name} import failed: {e}")
        
        # 4. Required Directories Check
        required_dirs = [
            settings.MEDIA_ROOT,
            settings.STATIC_ROOT,
            settings.BASE_DIR / 'static',
            settings.BASE_DIR / 'logs',
            settings.BASE_DIR / 'templates'
        ]
        
        for dir_path in required_dirs:
            if os.path.exists(dir_path):
                successes.append(f"✓ Directory exists: {dir_path}")
            else:
                issues.append(f"✗ Missing directory: {dir_path}")
        
        # 5. Migration Status Check
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            pending_migrations = executor.migration_plan(executor.loader.graph.leaf_nodes())
            
            if not pending_migrations:
                successes.append("✓ All migrations applied")
            else:
                issues.append(f"✗ {len(pending_migrations)} pending migrations")
        except Exception as e:
            issues.append(f"✗ Migration check failed: {e}")
        
        # 6. Third-party Libraries Check
        libraries_to_check = [
            ('rest_framework', 'Django REST Framework'),
            ('corsheaders', 'CORS Headers'),
            ('graphene_django', 'Graphene Django'),
            ('celery', 'Celery'),
            ('psycopg2', 'PostgreSQL adapter'),
            ('redis', 'Redis client'),
            ('pytesseract', 'PyTesseract'),
            ('PIL', 'Pillow'),
        ]
        
        # Special handling for PDF libraries
        try:
            import PyPDF2
            successes.append("✓ PyPDF2 available")
        except ImportError:
            issues.append("✗ PyPDF2 not available")
            
        try:
            import fitz
            successes.append("✓ PyMuPDF (fitz) available")
        except ImportError:
            issues.append("✗ PyMuPDF not available")
        
        for lib_name, display_name in libraries_to_check:
            try:
                __import__(lib_name)
                successes.append(f"✓ {display_name} available")
            except ImportError:
                issues.append(f"✗ {display_name} not available")
        
        # 7. URL Configuration Test
        try:
            from django.urls import reverse
            from django.test import Client
            
            # Test some basic URLs
            test_urls = [
                ('admin:index', 'Admin interface'),
                ('health-check', 'Health check endpoint'),
            ]
            
            for url_name, description in test_urls:
                try:
                    reverse(url_name)
                    successes.append(f"✓ URL configured: {description}")
                except Exception:
                    issues.append(f"✗ URL not configured: {description}")
        except Exception as e:
            issues.append(f"✗ URL configuration test failed: {e}")
        
        # 8. Celery Configuration Check
        try:
            from celery import current_app
            if hasattr(settings, 'CELERY_BROKER_URL'):
                successes.append("✓ Celery configuration present")
            else:
                issues.append("✗ Celery configuration missing")
        except Exception as e:
            issues.append(f"✗ Celery check failed: {e}")
        
        # 9. Environment Variables Check
        env_vars_to_check = [
            ('SECRET_KEY', 'SECRET_KEY'),
            ('DB_NAME', 'Database name'),
            ('DB_USER', 'Database user'),
            ('DB_PASSWORD', 'Database password'),
        ]
        
        for var_name, description in env_vars_to_check:
            # Check if it's in settings or environment
            if (hasattr(settings, var_name) and getattr(settings, var_name)) or os.getenv(var_name):
                successes.append(f"✓ {description} configured")
            else:
                # Check if using config() with defaults (which means it's working)
                try:
                    from decouple import config
                    test_value = config(var_name, default=None)
                    if test_value is not None:
                        successes.append(f"✓ {description} configured (using defaults)")
                    else:
                        issues.append(f"✗ Missing environment variable: {var_name}")
                except:
                    issues.append(f"✗ Missing environment variable: {var_name}")
        
        # Output Results
        self.stdout.write(self.style.SUCCESS(f"\n=== SUCCESSES ({len(successes)}) ==="))
        for success in successes:
            self.stdout.write(success)
        
        if issues:
            self.stdout.write(self.style.ERROR(f"\n=== ISSUES ({len(issues)}) ==="))
            for issue in issues:
                self.stdout.write(issue)
        else:
            self.stdout.write(self.style.SUCCESS("\n=== NO ISSUES FOUND ==="))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n=== SUMMARY ==="))
        self.stdout.write(f"✓ Successes: {len(successes)}")
        self.stdout.write(f"✗ Issues: {len(issues)}")
        
        if len(issues) == 0:
            self.stdout.write(self.style.SUCCESS("\n🎉 BACKEND IS FULLY CONFIGURED AND READY!"))
        elif len(issues) <= 3:
            self.stdout.write(self.style.WARNING("\n⚠️  BACKEND IS MOSTLY READY WITH MINOR ISSUES"))
        else:
            self.stdout.write(self.style.ERROR("\n❌ BACKEND NEEDS ATTENTION"))
            
        # Don't return an integer, just finish
        self.stdout.write("\n=== HEALTH CHECK COMPLETE ===")
        
        if len(issues) > 0:
            sys.exit(1)
        else:
            sys.exit(0)
