from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from reports.models import ReportTemplate
from dashboard.models import ExpenseCategory
import json


class Command(BaseCommand):
    help = 'Setup initial data for the accounting system - debug version'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up initial data...'))
        
        try:
            with transaction.atomic():
                # Create expense categories
                self.stdout.write('Step 1: Creating expense categories...')
                self.create_expense_categories()
                
                # Create report templates
                self.stdout.write('Step 2: Creating report templates...')
                self.create_report_templates()
                
                # Create superuser if requested
                if options['create_superuser']:
                    self.stdout.write('Step 3: Creating superuser...')
                    self.create_superuser()
                else:
                    self.stdout.write('Step 3: Skipping superuser creation (not requested)')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in setup: {str(e)}'))
            import traceback
            traceback.print_exc()
        
        self.stdout.write(self.style.SUCCESS('Initial data setup completed successfully!'))

    def create_expense_categories(self):
        """Create default expense categories"""
        categories = [
            {'name': 'Office Supplies', 'description': 'Stationery, equipment, and office materials'},
            {'name': 'Travel & Entertainment', 'description': 'Business travel and client entertainment'},
            {'name': 'Professional Services', 'description': 'Legal, consulting, and professional fees'},
            {'name': 'Utilities', 'description': 'Electricity, water, internet, and phone bills'},
            {'name': 'Marketing & Advertising', 'description': 'Promotional materials and advertising costs'},
            {'name': 'Software & Subscriptions', 'description': 'Software licenses and subscription services'},
            {'name': 'Equipment & Hardware', 'description': 'Computer equipment and hardware purchases'},
            {'name': 'Insurance', 'description': 'Business insurance premiums'},
            {'name': 'Rent & Facilities', 'description': 'Office rent and facility costs'},
            {'name': 'Other', 'description': 'Miscellaneous business expenses'},
        ]
        
        created_count = 0
        for category_data in categories:
            category, created = ExpenseCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={'description': category_data['description']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created category: {category.name}')
            else:
                self.stdout.write(f'  Category already exists: {category.name}')
        
        self.stdout.write(f'Created {created_count} new expense categories')

    def create_report_templates(self):
        """Create default report templates"""
        self.stdout.write('Creating report templates...')
        templates = [
            {
                'name': 'Financial Overview Report',
                'description': 'Comprehensive financial overview with revenue, expenses, and profit analysis',
                'template_type': 'financial_overview',
                'template_config': {
                    'parameters_schema': {
                        'type': 'object',
                        'properties': {
                            'date_from': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'Start date for the report period'
                            },
                            'date_to': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'End date for the report period'
                            }
                        },
                        'required': ['date_from', 'date_to']
                    }
                },
                'chart_types': ['pie', 'bar', 'line']
            },
            {
                'name': 'Expense Analysis Report',
                'description': 'Detailed analysis of expenses by category and time period',
                'template_type': 'expense_analysis',
                'template_config': {
                    'parameters_schema': {
                        'type': 'object',
                        'properties': {
                            'date_from': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'Start date for the report period'
                            },
                            'date_to': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'End date for the report period'
                            }
                        },
                        'required': ['date_from', 'date_to']
                    }
                },
                'chart_types': ['pie', 'bar', 'line']
            }
        ]
        
        templates_created = 0
        for template_data in templates:
            try:
                template, created = ReportTemplate.objects.get_or_create(
                    name=template_data['name'],
                    defaults={
                        'description': template_data['description'],
                        'template_type': template_data['template_type'],
                        'template_config': template_data['template_config'],
                        'chart_types': template_data.get('chart_types', []),
                        'include_charts': True,
                        'include_summary': True,
                        'include_detailed_data': True,
                        'include_exceptions': True,
                        'include_recommendations': False,
                        'is_active': True,
                        'is_public': True
                    }
                )
                if created:
                    templates_created += 1
                    self.stdout.write(f'Created report template: {template.name}')
                else:
                    self.stdout.write(f'  Template already exists: {template.name}')
            except Exception as e:
                self.stdout.write(f'Error creating template {template_data["name"]}: {str(e)}')
        
        self.stdout.write(f'Created {templates_created} new report templates')

    def create_superuser(self):
        """Create a superuser account"""
        username = 'admin'
        email = 'admin@example.com'
        password = 'admin123'
        
        try:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'Superuser "{username}" already exists')
                return
            
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superuser created successfully!\n'
                    f'Username: {username}\n'
                    f'Email: {email}\n'
                    f'Password: {password}\n'
                    f'Please change the password after first login!'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create superuser: {str(e)}')
            )
