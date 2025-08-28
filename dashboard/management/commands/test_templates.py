from django.core.management.base import BaseCommand
from django.db import transaction
from reports.models import ReportTemplate

class Command(BaseCommand):
    help = 'Test report template creation'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing report template creation...'))
        
        template_data = {
            'name': 'Test Financial Report',
            'description': 'Test report template',
            'template_type': 'test_financial',
            'template_config': {
                'parameters_schema': {
                    'type': 'object',
                    'properties': {
                        'date_from': {
                            'type': 'string',
                            'format': 'date'
                        }
                    }
                }
            },
            'chart_types': ['pie']
        }
        
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
                self.stdout.write(f'✓ Created report template: {template.name}')
            else:
                self.stdout.write(f'✓ Template already exists: {template.name}')
                
            # Count total templates
            total_templates = ReportTemplate.objects.count()
            self.stdout.write(f'Total report templates in database: {total_templates}')
            
        except Exception as e:
            self.stdout.write(f'✗ Error creating template: {str(e)}')
            import traceback
            traceback.print_exc()
