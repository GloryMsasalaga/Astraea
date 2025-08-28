from rest_framework import serializers
from .models import ReportTemplate, GeneratedReport, ReportSection, ReportChart, ReportDownload


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for report templates"""
    
    class Meta:
        model = ReportTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'category',
            'parameters_schema', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReportSectionSerializer(serializers.ModelSerializer):
    """Serializer for report sections"""
    
    class Meta:
        model = ReportSection
        fields = [
            'id', 'name', 'content', 'order', 'section_type'
        ]
        read_only_fields = ['id']


class ReportChartSerializer(serializers.ModelSerializer):
    """Serializer for report charts"""
    
    class Meta:
        model = ReportChart
        fields = [
            'id', 'title', 'chart_type', 'data', 'options', 'order'
        ]
        read_only_fields = ['id']


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Serializer for generated reports"""
    template = ReportTemplateSerializer(read_only=True)
    sections = ReportSectionSerializer(many=True, read_only=True)
    charts = ReportChartSerializer(many=True, read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'user', 'template', 'title', 'parameters', 'status',
            'progress', 'format', 'file_path', 'file_size', 'error_message',
            'sections', 'charts', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'progress', 'file_path', 'file_size',
            'error_message', 'sections', 'charts', 'created_at', 'updated_at',
            'completed_at'
        ]


class ReportGenerationRequestSerializer(serializers.Serializer):
    """Serializer for report generation requests"""
    template_id = serializers.UUIDField(required=True)
    title = serializers.CharField(max_length=255, required=True)
    parameters = serializers.JSONField(required=False, default=dict)
    format = serializers.ChoiceField(
        choices=['pdf', 'html', 'excel'],
        default='pdf',
        required=False
    )
    
    def validate_template_id(self, value):
        """Validate that the template exists and is active"""
        try:
            template = ReportTemplate.objects.get(id=value, is_active=True)
            return value
        except ReportTemplate.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive template ID")
    
    def validate_parameters(self, value):
        """Validate parameters against template schema"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object")
        
        # Get template to validate against schema
        template_id = self.initial_data.get('template_id')
        if template_id:
            try:
                template = ReportTemplate.objects.get(id=template_id, is_active=True)
                schema = template.parameters_schema or {}
                
                # Basic validation - check required parameters
                required_params = schema.get('required', [])
                for param in required_params:
                    if param not in value:
                        raise serializers.ValidationError(
                            f"Missing required parameter: {param}"
                        )
                
                # Validate parameter types if defined
                properties = schema.get('properties', {})
                for param, param_value in value.items():
                    if param in properties:
                        param_schema = properties[param]
                        param_type = param_schema.get('type')
                        
                        if param_type == 'string' and not isinstance(param_value, str):
                            raise serializers.ValidationError(
                                f"Parameter '{param}' must be a string"
                            )
                        elif param_type == 'number' and not isinstance(param_value, (int, float)):
                            raise serializers.ValidationError(
                                f"Parameter '{param}' must be a number"
                            )
                        elif param_type == 'boolean' and not isinstance(param_value, bool):
                            raise serializers.ValidationError(
                                f"Parameter '{param}' must be a boolean"
                            )
                        elif param_type == 'array' and not isinstance(param_value, list):
                            raise serializers.ValidationError(
                                f"Parameter '{param}' must be an array"
                            )
                        elif param_type == 'object' and not isinstance(param_value, dict):
                            raise serializers.ValidationError(
                                f"Parameter '{param}' must be an object"
                            )
                
            except ReportTemplate.DoesNotExist:
                pass  # Template validation will be handled by template_id validator
        
        return value


class ReportDownloadSerializer(serializers.ModelSerializer):
    """Serializer for report downloads"""
    report_title = serializers.CharField(source='report.title', read_only=True)
    
    class Meta:
        model = ReportDownload
        fields = [
            'id', 'report', 'report_title', 'user', 'downloaded_at',
            'ip_address', 'user_agent'
        ]
        read_only_fields = ['id', 'downloaded_at']
