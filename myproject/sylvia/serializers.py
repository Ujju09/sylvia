from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Depot, Product, Dealer, Vehicle, Order, OrderItem, 
    MRN, Invoice, AuditLog, AppSettings, NotificationTemplate, DealerContext, OrderMRNImage
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']
        read_only_fields = ['id', 'is_staff']


class DepotSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Depot
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state', 'pincode', 
            'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class ProductSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'code', 'description', 'unit', 'is_active',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class DealerSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    whatsapp_display = serializers.CharField(source='get_whatsapp_number', read_only=True)
    
    class Meta:
        model = Dealer
        fields = [
            'id', 'name', 'code', 'contact_person', 'phone', 'whatsapp_number',
            'whatsapp_display', 'email', 'address', 'city', 'state', 'pincode',
            'gstin', 'is_active', 'credit_limit', 'credit_days',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'whatsapp_display']


class VehicleSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'truck_number', 'owner_name', 'driver_name', 'driver_phone',
            'capacity', 'vehicle_type', 'is_active',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='get_total_value')
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_id', 'quantity', 'unit_price', 'total_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_value']


class MRNSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    
    class Meta:
        model = MRN
        fields = [
            'id', 'mrn_number', 'mrn_date', 'status', 'quality_checked',
            'quality_remarks', 'approved_by', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'mrn_number', 'created_at', 'updated_at', 'created_by']


class InvoiceSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    balance_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='get_balance_amount')
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date', 'subtotal',
            'tax_amount', 'total_amount', 'status', 'payment_received',
            'payment_date', 'balance_amount', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at', 'created_by', 'balance_amount']


class OrderMRNImageSerializer(serializers.ModelSerializer):
    """Serializer for MRN proof images"""
    created_by = UserSerializer(read_only=True)
    secure_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderMRNImage
        fields = [
            'id', 'order', 'image_url', 'secure_image_url', 'image_type', 'original_filename',
            'file_size', 'upload_timestamp', 'description', 'is_primary',
            'storage_key', 'content_type', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'upload_timestamp', 'created_at', 'updated_at', 'created_by']
    
    def get_secure_image_url(self, obj):
        """Generate secure presigned URL for direct image access"""
        try:
            if obj.storage_key:
                from .storage import krutrim_storage
                # Generate presigned URL that expires in 1 hour
                presigned_url = krutrim_storage.generate_presigned_url(obj.storage_key, expiration=3600)
                if presigned_url:
                    return presigned_url
            
            # Fallback to proxy service if presigned URL fails
            request = self.context.get('request')
            if request:
                from django.urls import reverse
                return request.build_absolute_uri(
                    reverse('ordermrnimage-serve-image', kwargs={'pk': obj.pk})
                )
        except Exception as e:
            # If anything fails, fallback to proxy service
            request = self.context.get('request')
            if request:
                from django.urls import reverse
                return request.build_absolute_uri(
                    reverse('ordermrnimage-serve-image', kwargs={'pk': obj.pk})
                )
        
        return None


class OrderSerializer(serializers.ModelSerializer):
    dealer = DealerSerializer(read_only=True)
    dealer_id = serializers.IntegerField(write_only=True)
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.IntegerField(write_only=True)
    depot = DepotSerializer(read_only=True)
    depot_id = serializers.IntegerField(write_only=True)
    created_by = UserSerializer(read_only=True)
    
    order_items = OrderItemSerializer(many=True, read_only=True)
    mrn = MRNSerializer(read_only=True)
    invoice = InvoiceSerializer(read_only=True)
    mrn_images = OrderMRNImageSerializer(many=True, read_only=True)
    primary_mrn_image = serializers.SerializerMethodField()
    
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source='get_total_quantity')
    total_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, source='get_total_value')
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'dealer', 'dealer_id', 'vehicle', 'vehicle_id',
            'depot', 'depot_id', 'order_date', 'mrn_date', 'bill_date',
            'dispatch_date', 'delivery_date', 'status', 'remarks',
            'whatsapp_sent', 'whatsapp_sent_at', 'order_items', 'mrn', 'invoice',
            'mrn_images', 'primary_mrn_image', 'total_quantity', 'total_value', 
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'id', 'order_number', 'created_at', 'updated_at', 'created_by',
            'total_quantity', 'total_value', 'primary_mrn_image'
        ]
    
    def get_primary_mrn_image(self, obj):
        """Get the primary MRN image for this order"""
        primary_image = obj.mrn_images.filter(is_primary=True).first()
        return OrderMRNImageSerializer(primary_image).data if primary_image else None


class OrderCreateSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = [
            'dealer', 'vehicle', 'depot', 'order_date', 'remarks', 'order_items'
        ]
    
    def create(self, validated_data):
        order_items_data = validated_data.pop('order_items')
        order = Order.objects.create(**validated_data)
        
        for item_data in order_items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        return order


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'action', 'model_name', 'object_id', 'user', 'details',
            'ip_address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppSettingsSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = AppSettings
        fields = [
            'id', 'key', 'value', 'description', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'type', 'subject', 'template_content', 'variables',
            'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


# Dashboard/Analytics serializers
class DashboardStatsSerializer(serializers.Serializer):
    orders_created_today = serializers.IntegerField()
    mrn_approved_today = serializers.IntegerField()
    orders_billed_today = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    active_dealers = serializers.IntegerField()
    active_vehicles = serializers.IntegerField()


class DealerStatsSerializer(serializers.Serializer):
    dealer_id = serializers.IntegerField()
    dealer_name = serializers.CharField()
    weekly_orders = serializers.IntegerField()
    monthly_orders = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    avg_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)


class ProductStatsSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    avg_quantity_per_order = serializers.DecimalField(max_digits=10, decimal_places=2)



class DealerContextSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    dealer = DealerSerializer(read_only=True)
    dealer_id = serializers.IntegerField(write_only=True)
    products_mentioned = ProductSerializer(many=True, read_only=True)
    products_mentioned_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    structured_trait_scores = serializers.SerializerMethodField()
    understanding_summary = serializers.SerializerMethodField()
    follow_up_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = DealerContext
        fields = [
            'id', 'dealer', 'dealer_id', 'interaction_type', 'interaction_date',
            'interaction_summary', 'detailed_notes', 'sentiment', 'priority_level',
            
            # Structured trait scores
            'reliability_score', 'communication_clarity', 'payment_punctuality',
            'order_consistency', 'trust_level', 'openness_to_feedback',
            'cooperation_level', 'loyalty_tendency',
            
            # Understanding-focused fields
            'primary_motivations', 'business_challenges', 'success_metrics',
            'concerns_expressed', 'aspirations_goals', 'preferred_communication_style',
            'decision_making_process', 'information_preferences', 'timing_preferences',
            
            # Business context
            'topics_discussed', 'products_mentioned', 'products_mentioned_ids',
            'follow_up_required', 'follow_up_date', 'follow_up_notes',
            
            # Assessment and outcome
            'intuitive_assessment', 'issue_resolved', 'resolution_notes',
            'outcome', 'understanding_gained', 'tags',
            
            # Computed fields
            'structured_trait_scores', 'understanding_summary', 'follow_up_overdue',
            
            # Base model fields
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'structured_trait_scores',
            'understanding_summary', 'follow_up_overdue'
        ]
    
    def get_structured_trait_scores(self, obj):
        """Get structured trait scores summary"""
        return obj.get_structured_trait_scores()
    
    def get_understanding_summary(self, obj):
        """Get understanding summary"""
        return obj.get_understanding_summary()
    
    def get_follow_up_overdue(self, obj):
        """Check if follow-up is overdue"""
        return obj.get_follow_up_status()
    
    def create(self, validated_data):
        products_mentioned_ids = validated_data.pop('products_mentioned_ids', [])
        context = DealerContext.objects.create(**validated_data)
        
        if products_mentioned_ids:
            context.products_mentioned.set(products_mentioned_ids)
        
        return context