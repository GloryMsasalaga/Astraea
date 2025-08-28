from rest_framework import serializers
from .models import Document, ExtractedField, ProcessingJob


class ExtractedFieldSerializer(serializers.ModelSerializer):
    """Serializer for extracted fields"""
    
    class Meta:
        model = ExtractedField
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProcessingJobSerializer(serializers.ModelSerializer):
    """Serializer for processing jobs"""
    
    class Meta:
        model = ProcessingJob
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'started_at', 'completed_at')


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for documents"""
    
    extracted_fields = ExtractedFieldSerializer(many=True, read_only=True)
    processing_jobs = ProcessingJobSerializer(many=True, read_only=True)
    file_size = serializers.ReadOnlyField()
    file_extension = serializers.ReadOnlyField()
    
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ('id', 'uploaded_by', 'created_at', 'updated_at', 'processed_at')
    
    def create(self, validated_data):
        """Create document with uploaded_by field set to current user"""
        validated_data['uploaded_by'] = self.context['request'].user
        validated_data['original_filename'] = validated_data['file'].name
        return super().create(validated_data)


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload"""
    
    file = serializers.FileField()
    document_type = serializers.ChoiceField(choices=Document.DOCUMENT_TYPES, default='other')
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (10MB limit)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must be under 10MB")
        
        # Check file extension
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        file_extension = value.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise serializers.ValidationError(
                f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        return value


class FieldValidationSerializer(serializers.Serializer):
    """Serializer for field validation"""
    
    field_value = serializers.CharField()
    is_valid = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)
