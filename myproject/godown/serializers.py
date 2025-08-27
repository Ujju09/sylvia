from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    GodownLocation, ItemCategory, Item, Stock, StockBatch,
    StockTransaction, StockAlert, StockMovementLog
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class GodownLocationSerializer(serializers.ModelSerializer):
    """Serializer for GodownLocation model"""
    manager = UserSerializer(read_only=True)
    manager_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = GodownLocation
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state', 'pincode',
            'latitude', 'longitude', 'total_capacity', 'manager', 'manager_id',
            'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class GodownLocationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing godowns"""
    manager = UserSerializer(read_only=True)
    
    class Meta:
        model = GodownLocation
        fields = [
            'id', 'name', 'code', 'city', 'state', 'manager', 'is_active'
        ]


class ItemCategorySerializer(serializers.ModelSerializer):
    """Serializer for ItemCategory model"""
    created_by = UserSerializer(read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ItemCategory
        fields = [
            'id', 'name', 'code', 'description', 'is_active',
            'created_at', 'updated_at', 'created_by', 'items_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_items_count(self, obj):
        return obj.items.filter(is_active=True).count()


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for Item model"""
    category = ItemCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    created_by = UserSerializer(read_only=True)
    total_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = Item
        fields = [
            'id', 'name', 'sku', 'description', 'category', 'category_id',
            'unit_of_measurement', 'minimum_stock_level', 'maximum_stock_level',
            'unit_price', 'barcode', 'expiry_tracking_enabled', 'is_active',
            'created_at', 'updated_at', 'created_by', 'total_stock'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_total_stock(self, obj):
        return sum(stock.quantity for stock in obj.stock_levels.all())


class ItemListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing items"""
    category = ItemCategorySerializer(read_only=True)
    
    class Meta:
        model = Item
        fields = [
            'id', 'name', 'sku', 'category', 'unit_of_measurement',
            'minimum_stock_level', 'is_active'
        ]


class StockBatchSerializer(serializers.ModelSerializer):
    """Serializer for StockBatch model"""
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StockBatch
        fields = [
            'id', 'batch_number', 'manufacture_date', 'expiry_date',
            'quantity', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class StockSerializer(serializers.ModelSerializer):
    """Serializer for Stock model"""
    godown = GodownLocationListSerializer(read_only=True)
    godown_id = serializers.IntegerField(write_only=True)
    item = ItemListSerializer(read_only=True)
    item_id = serializers.IntegerField(write_only=True)
    created_by = UserSerializer(read_only=True)
    batches = StockBatchSerializer(many=True, read_only=True)
    
    class Meta:
        model = Stock
        fields = [
            'id', 'godown', 'godown_id', 'item', 'item_id', 'quantity',
            'reserved_quantity', 'available_quantity', 'last_updated',
            'created_at', 'updated_at', 'created_by', 'batches'
        ]
        read_only_fields = [
            'available_quantity', 'last_updated', 'created_at', 'updated_at', 'created_by'
        ]


class StockListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing stock"""
    godown = GodownLocationListSerializer(read_only=True)
    item = ItemListSerializer(read_only=True)
    low_stock_alert = serializers.SerializerMethodField()
    
    class Meta:
        model = Stock
        fields = [
            'id', 'godown', 'item', 'quantity', 'available_quantity',
            'last_updated', 'low_stock_alert'
        ]
    
    def get_low_stock_alert(self, obj):
        return obj.quantity <= obj.item.minimum_stock_level


class StockTransactionSerializer(serializers.ModelSerializer):
    """Serializer for StockTransaction model"""
    godown = GodownLocationListSerializer(read_only=True)
    godown_id = serializers.IntegerField(write_only=True)
    item = ItemListSerializer(read_only=True)
    item_id = serializers.IntegerField(write_only=True)
    source_godown = GodownLocationListSerializer(read_only=True)
    source_godown_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    destination_godown = GodownLocationListSerializer(read_only=True)
    destination_godown_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StockTransaction
        fields = [
            'id', 'transaction_id', 'transaction_type', 'status',
            'godown', 'godown_id', 'item', 'item_id', 'quantity',
            'source_godown', 'source_godown_id', 'destination_godown', 'destination_godown_id',
            'reference_number', 'reference_document', 'batch_number', 'notes',
            'transaction_date', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'transaction_id', 'created_at', 'updated_at', 'created_by'
        ]
    
    def validate(self, data):
        """Validate transaction data"""
        transaction_type = data.get('transaction_type')
        
        if transaction_type in ['TRANSFER_OUT', 'TRANSFER_IN']:
            if not data.get('source_godown_id') or not data.get('destination_godown_id'):
                raise serializers.ValidationError(
                    "Source and destination godowns are required for transfer transactions"
                )
            
            if data.get('source_godown_id') == data.get('destination_godown_id'):
                raise serializers.ValidationError(
                    "Source and destination godowns cannot be the same"
                )
        
        return data


class StockTransactionListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing transactions"""
    godown = GodownLocationListSerializer(read_only=True)
    item = ItemListSerializer(read_only=True)
    source_godown = GodownLocationListSerializer(read_only=True)
    destination_godown = GodownLocationListSerializer(read_only=True)
    
    class Meta:
        model = StockTransaction
        fields = [
            'id', 'transaction_id', 'transaction_type', 'status',
            'godown', 'item', 'quantity', 'source_godown', 'destination_godown',
            'transaction_date'
        ]


class StockAlertSerializer(serializers.ModelSerializer):
    """Serializer for StockAlert model"""
    godown = GodownLocationListSerializer(read_only=True)
    godown_id = serializers.IntegerField(write_only=True)
    item = ItemListSerializer(read_only=True)
    item_id = serializers.IntegerField(write_only=True)
    acknowledged_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StockAlert
        fields = [
            'id', 'alert_type', 'severity', 'status', 'godown', 'godown_id',
            'item', 'item_id', 'current_quantity', 'threshold_quantity',
            'message', 'acknowledged_by', 'acknowledged_at', 'resolved_at',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by', 'acknowledged_by',
            'acknowledged_at', 'resolved_at'
        ]


class StockMovementLogSerializer(serializers.ModelSerializer):
    """Serializer for StockMovementLog model"""
    transaction = StockTransactionListSerializer(read_only=True)
    stock = StockListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StockMovementLog
        fields = [
            'id', 'transaction', 'stock', 'quantity_before',
            'quantity_after', 'quantity_changed',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustment operations"""
    adjustment_type = serializers.ChoiceField(choices=[
        ('ADD', 'Add Stock'),
        ('REMOVE', 'Remove Stock'),
        ('SET', 'Set Stock Level')
    ])
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0)
    reason = serializers.CharField(max_length=200, required=False)
    reference_number = serializers.CharField(max_length=100, required=False)
    batch_number = serializers.CharField(max_length=100, required=False)


class StockTransferSerializer(serializers.Serializer):
    """Serializer for stock transfer operations"""
    source_godown_id = serializers.IntegerField()
    destination_godown_id = serializers.IntegerField()
    item_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    reference_number = serializers.CharField(max_length=100, required=False)
    batch_number = serializers.CharField(max_length=100, required=False)
    notes = serializers.CharField(required=False)
    
    def validate(self, data):
        if data['source_godown_id'] == data['destination_godown_id']:
            raise serializers.ValidationError(
                "Source and destination godowns cannot be the same"
            )
        return data


class StockReportSerializer(serializers.Serializer):
    """Serializer for stock report parameters"""
    godown_id = serializers.IntegerField(required=False)
    item_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    low_stock_only = serializers.BooleanField(default=False)
    include_inactive = serializers.BooleanField(default=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)