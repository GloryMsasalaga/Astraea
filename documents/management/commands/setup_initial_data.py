from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboard.models import ExpenseCategory
from django.db import transaction


class Command(BaseCommand):
    help = 'Setup initial data for the accounting system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username for superuser',
            default='admin'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for superuser',
            default='admin@example.com'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for superuser',
            default='admin123'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up initial data...'))
        
        with transaction.atomic():
            # Create default expense categories
            self.create_expense_categories()
            
            # Create superuser if requested
            if options['create_superuser']:
                self.create_superuser(
                    options['username'],
                    options['email'],
                    options['password']
                )
        
        self.stdout.write(self.style.SUCCESS('Initial setup completed successfully!'))
    
    def create_expense_categories(self):
        """Create default expense categories"""
        
        categories = [
            {
                'name': 'Office Supplies',
                'description': 'General office supplies and materials',
                'color_code': '#3498db',
                'monthly_budget': 500.00
            },
            {
                'name': 'Travel & Transportation',
                'description': 'Business travel, transportation, and vehicle expenses',
                'color_code': '#e74c3c',
                'monthly_budget': 1000.00
            },
            {
                'name': 'Marketing & Advertising',
                'description': 'Marketing campaigns, advertising, and promotional expenses',
                'color_code': '#f39c12',
                'monthly_budget': 2000.00
            },
            {
                'name': 'Professional Services',
                'description': 'Legal, accounting, consulting, and other professional services',
                'color_code': '#9b59b6',
                'monthly_budget': 1500.00
            },
            {
                'name': 'Utilities',
                'description': 'Electricity, water, internet, phone, and other utilities',
                'color_code': '#1abc9c',
                'monthly_budget': 800.00
            },
            {
                'name': 'Rent & Facilities',
                'description': 'Office rent, building maintenance, and facility costs',
                'color_code': '#34495e',
                'monthly_budget': 5000.00
            },
            {
                'name': 'Equipment & Technology',
                'description': 'Computer equipment, software, and technology expenses',
                'color_code': '#16a085',
                'monthly_budget': 1200.00
            },
            {
                'name': 'Insurance',
                'description': 'Business insurance premiums and coverage',
                'color_code': '#8e44ad',
                'monthly_budget': 600.00
            },
            {
                'name': 'Training & Education',
                'description': 'Employee training, courses, and educational expenses',
                'color_code': '#27ae60',
                'monthly_budget': 400.00
            },
            {
                'name': 'Miscellaneous',
                'description': 'Other business expenses not covered by specific categories',
                'color_code': '#95a5a6',
                'monthly_budget': 300.00
            }
        ]
        
        created_count = 0
        for cat_data in categories:
            category, created = ExpenseCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'color_code': cat_data['color_code'],
                    'monthly_budget': cat_data['monthly_budget'],
                    'yearly_budget': cat_data['monthly_budget'] * 12
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"  Created category: {category.name}")
            else:
                self.stdout.write(f"  Category already exists: {category.name}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} new expense categories')
        )
    
    def create_superuser(self, username, email, password):
        """Create superuser account"""
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{username}" already exists')
            )
            return
        
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created superuser: {username}')
        )
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Email: {email}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(
            self.style.WARNING(
                'Please change the default password after first login!'
            )
        )
