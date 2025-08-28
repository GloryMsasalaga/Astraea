from rest_framework import serializers
from .models import (
    ReconciliationSession, 
    LedgerRecord, 
    BankRecord, 
    TransactionMatch, 
    ReconciliationException
)


class LedgerRecordSerializer(serializers.ModelSerializer):
    """Serializer for ledger records"""
    
    class Meta:
        model = LedgerRecord
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class BankRecordSerializer(serializers.ModelSerializer):
    """Serializer for bank records"""
    
    class Meta:
        model = BankRecord
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class TransactionMatchSerializer(serializers.ModelSerializer):
    """Serializer for transaction matches"""
    
    ledger_record = LedgerRecordSerializer(read_only=True)
    bank_record = BankRecordSerializer(read_only=True)
    
    class Meta:
        model = TransactionMatch
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class ReconciliationExceptionSerializer(serializers.ModelSerializer):
    """Serializer for reconciliation exceptions"""
    
    ledger_record = LedgerRecordSerializer(read_only=True)
    bank_record = BankRecordSerializer(read_only=True)
    
    class Meta:
        model = ReconciliationException
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class ReconciliationSessionSerializer(serializers.ModelSerializer):
    """Serializer for reconciliation sessions"""
    
    ledger_records = LedgerRecordSerializer(many=True, read_only=True)
    bank_records = BankRecordSerializer(many=True, read_only=True)
    matches = TransactionMatchSerializer(many=True, read_only=True)
    exceptions = ReconciliationExceptionSerializer(many=True, read_only=True)
    match_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = ReconciliationSession
        fields = '__all__'
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at', 'processed_at')
    
    def create(self, validated_data):
        """Create session with created_by field set to current user"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class FileUploadSerializer(serializers.Serializer):
    """Serializer for reconciliation file upload"""
    
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    ledger_file = serializers.FileField()
    bank_statement_file = serializers.FileField()
    date_tolerance_days = serializers.IntegerField(default=0, min_value=0, max_value=30)
    amount_tolerance = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00, min_value=0)
    
    def validate_ledger_file(self, value):
        """Validate ledger file"""
        return self._validate_file(value, 'ledger')
    
    def validate_bank_statement_file(self, value):
        """Validate bank statement file"""
        return self._validate_file(value, 'bank statement')
    
    def _validate_file(self, value, file_type):
        """Common file validation"""
        # Check file size (50MB limit)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError(f"{file_type.title()} file size must be under 50MB")
        
        # Check file extension
        allowed_extensions = ['.csv', '.xlsx', '.xls']
        file_extension = value.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise serializers.ValidationError(
                f"{file_type.title()} file type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        return value


class MatchConfirmationSerializer(serializers.Serializer):
    """Serializer for confirming transaction matches"""
    
    notes = serializers.CharField(required=False, allow_blank=True)


class ExceptionResolutionSerializer(serializers.Serializer):
    """Serializer for resolving reconciliation exceptions"""
    
    resolution_notes = serializers.CharField(required=False, allow_blank=True)
