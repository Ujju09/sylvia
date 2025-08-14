from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Source, CashCollect


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class SourceSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Source
        fields = [
            'id', 'text', 'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class CashCollectSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    received_by = UserSerializer(read_only=True)
    source = SourceSerializer(read_only=True)
    
    # Write-only fields for creating/updating
    source_id = serializers.IntegerField(write_only=True)
    received_by_id = serializers.IntegerField(write_only=True)
    
    # Additional display fields
    source_text = serializers.CharField(source='source.text', read_only=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True)
    
    class Meta:
        model = CashCollect
        fields = [
            'id', 'date', 'amount', 'note',
            'source', 'source_id', 'source_text',
            'received_by', 'received_by_id', 'received_by_username',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def validate_source_id(self, value):
        """Validate that the source exists and is active"""
        try:
            source = Source.objects.get(id=value)
            if not source.is_active:
                raise serializers.ValidationError("The selected source is not active.")
            return value
        except Source.DoesNotExist:
            raise serializers.ValidationError("Invalid source ID.")
    
    def validate_received_by_id(self, value):
        """Validate that the user exists"""
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user ID.")
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value


class CashCollectListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""
    source_text = serializers.CharField(source='source.text', read_only=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True)
    
    class Meta:
        model = CashCollect
        fields = [
            'id', 'date', 'amount', 'note',
            'source_text', 'received_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CashCollectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CashCollect records"""
    
    class Meta:
        model = CashCollect
        fields = ['date', 'source', 'amount', 'received_by', 'note']
    
    def validate_source(self, value):
        """Validate that the source is active"""
        if not value.is_active:
            raise serializers.ValidationError("The selected source is not active.")
        return value
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value