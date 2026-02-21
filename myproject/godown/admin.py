from django.contrib import admin
from .models import (
    GodownLocation, OrderInTransit, GodownInventory, CrossoverRecord,
    LoadingRequest, LoadingRequestImage, DeliveryChallan, DeliveryChallanItem, ChallanItemBatchMapping,
    NotificationLog, NotificationRecipient, GodownInventoryLedger, LedgerBatchMapping,
    GodownDailyBalance, InventoryVariance
)


@admin.register(GodownLocation)
class GodownLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'organization', 'city', 'state', 'manager', 'is_active', 'created_at']
    list_filter = ['organization', 'is_active', 'city', 'state', 'created_at']
    search_fields = ['name', 'code', 'city', 'address']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['name']


@admin.register(OrderInTransit)
class OrderInTransitAdmin(admin.ModelAdmin):
    list_display = [
        'eway_bill_number', 'dispatch_id', 'organization', 'status', 'godown', 'actual_arrival_date', 'product',
        'expected_total_bags', 'actual_received_bags', 'good_bags'
    ]
    list_filter = [
        'organization', 'status', 'godown', 'crossover_required', 'actual_arrival_date'
    ]
    search_fields = [
        'eway_bill_number', 'transport_document_number',
        'order__order_number', 'order__dealer__name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['-dispatch_id']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('dispatch_id', 'eway_bill_number', 'transport_document_number', 'godown', 'status')
        }),
        
        ('Quantities', {
            'fields': (
                'product','expected_total_bags', 'actual_received_bags',
                'good_bags', 'damaged_bags', 'shortage_bags', 'excess_bags'
            )
        }),
        
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(GodownInventory)
class GodownInventoryAdmin(admin.ModelAdmin):
    list_display = [
        'batch_id', 'organization', 'godown', 'product', 'status',
        'good_bags_available', 'good_bags_reserved', 'damaged_bags',
        'received_date', 'quality_grade'
    ]
    list_filter = [
        'organization', 'status', 'godown', 'product', 'quality_grade',
        'received_date', 'expiry_alert_date'
    ]
    search_fields = [
        'batch_id', 'godown__name', 'product__name',
        'order_in_transit__eway_bill_number', 'storage_location'
    ]
    readonly_fields = ['batch_id', 'received_date', 'created_at', 'updated_at', 'created_by']
    ordering = ['received_date']  # FIFO ordering
    
    fieldsets = (
        ('Identification', {
            'fields': ('batch_id', 'godown', 'product', 'order_in_transit', 'status')
        }),
        ('Quantities', {
            'fields': (
                'total_bags_received', 'good_bags_available',
                'good_bags_reserved', 'damaged_bags'
            )
        }),
        ('Storage Details', {
            'fields': ('storage_location', 'quality_grade'),
        }),
        ('Dates', {
            'fields': ('received_date', 'manufacturing_date', 'expiry_alert_date')
        }),
        ('Notes', {
            'fields': ('storage_notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(CrossoverRecord)
class CrossoverRecordAdmin(admin.ModelAdmin):
    list_display = [
        'crossover_id', 'organization', 'destination_dealer', 'product',
        'requested_bags', 'actual_transferred_bags',
    ]
    list_filter = [
        'organization', 'destination_dealer', 'product',
        'approved_date'
    ]
    search_fields = [
        'crossover_id', 'destination_dealer__name'
    ]
    readonly_fields = ['crossover_id', 'approved_date', 'created_at', 'updated_at', 'created_by']
    ordering = ['-approved_date']

    fieldsets = (
        ('Identification', {
            'fields': ('crossover_id', 'product')
        }),
      
        ('Quantities', {
            'fields': (
                'requested_bags', 'actual_transferred_bags'
            )
        }),
        ('Timeline and Authorisation', {
            'fields': (
                'approved_date','supervised_by'
            )
        })
    )


@admin.register(LoadingRequest)
class LoadingRequestAdmin(admin.ModelAdmin):
    list_display = [
        'loading_request_id', 'organization', 'godown', 'dealer', 'product',
        'requested_bags', 'loaded_bags', 'get_completion_status', 'created_at'
    ]
    list_filter = [
        'organization', 'godown', 'product', 'dealer', 'supervised_by', 'created_at'
    ]
    search_fields = [
        'loading_request_id', 'dealer__name', 'dealer__code',
        'product__name', 'godown__name', 'special_instructions', 'loading_notes'
    ]
    readonly_fields = [
        'loading_request_id', 'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-created_at']
    
    def get_completion_status(self, obj):
        """Show completion status with color coding"""
        if obj.requested_bags == 0:
            return "N/A"
        
        completion = (obj.loaded_bags / obj.requested_bags) * 100
        
        if completion >= 100:
            return f"✅ Complete ({completion:.0f}%)"
        elif completion > 0:
            return f"🟡 Partial ({completion:.0f}%)"
        else:
            return "⏳ Pending"
    
    get_completion_status.short_description = 'Status'
    get_completion_status.admin_order_field = 'loaded_bags'

    fieldsets = (
        ('Basic Information', {
            'fields': ('loading_request_id', 'godown', 'supervised_by')
        }),
        ('Request Details', {
            'fields': ('dealer', 'product')
        }),
        ('Quantities', {
            'fields': ('requested_bags', 'loaded_bags'),
            'description': 'Enter the number of bags requested and actually loaded'
        }),
        ('Instructions & Notes', {
            'fields': ('special_instructions', 'loading_notes'),
            'classes': ('collapse',),
            'description': 'Additional information about the loading operation'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(LoadingRequestImage)
class LoadingRequestImageAdmin(admin.ModelAdmin):
    list_display = [
        'loading_request', 'image_type', 'original_filename',
        'file_size', 'is_primary', 'upload_timestamp'
    ]
    list_filter = [
        'image_type', 'is_primary', 'upload_timestamp', 'loading_request__godown'
    ]
    search_fields = [
        'loading_request__loading_request_id', 'original_filename',
        'description', 'storage_key'
    ]
    readonly_fields = [
        'upload_timestamp', 'file_size', 'storage_key',
        'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-upload_timestamp']

    fieldsets = (
        ('Loading Request', {
            'fields': ('loading_request', 'image_type', 'is_primary')
        }),
        ('Image Details', {
            'fields': ('image_url', 'original_filename', 'file_size', 'content_type')
        }),
        ('Storage Information', {
            'fields': ('storage_key',),
            'classes': ('collapse',)
        }),
        ('Description', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('upload_timestamp', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(admin.ModelAdmin):
    list_display = [
        'challan_number', 'organization', 'challan_type', 'dealer', 'vehicle', 'status',
        'total_bags', 'total_weight_mt', 'issue_date'
    ]
    list_filter = [
        'organization', 'challan_type', 'status', 'godown', 'dealer',
        'issue_date', 'actual_delivery_date'
    ]
    search_fields = [
        'challan_number', 'dealer__name', 'vehicle__truck_number',
        'delivery_address', 'delivered_by', 'received_by'
    ]
    readonly_fields = [
        'challan_number', 'issue_date', 'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-issue_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('challan_number', 'challan_type', 'status', 'godown')
        }),
        ('Parties', {
            'fields': ('dealer', 'vehicle')
        }),
        ('Linked Operations', {
            'fields': ('crossover_record', 'loading_request'),
            'classes': ('collapse',)
        }),
        ('Quantities', {
            'fields': ('total_bags', 'total_weight_mt')
        }),
        ('Timeline', {
            'fields': ('issue_date', 'actual_delivery_date')
        }),
        ('Delivery Details', {
            'fields': ('delivery_address', 'special_instructions', 'remarks')
        }),
        ('Confirmation', {
            'fields': ('delivered_by', 'received_by'),
            'classes': ('collapse',)
        })
    )


class ChallanItemBatchMappingInline(admin.TabularInline):
    model = ChallanItemBatchMapping
    extra = 0
    readonly_fields = ['created_at', 'created_by']


@admin.register(DeliveryChallanItem)
class DeliveryChallanItemAdmin(admin.ModelAdmin):
    list_display = [
        'challan', 'product', 'bags', 'weight_per_bag_kg',
        'total_weight_mt'
    ]
    list_filter = ['product', 'challan__status', 'challan__issue_date']
    search_fields = [
        'challan__challan_number', 'product__name', 'quality_notes'
    ]
    readonly_fields = ['total_weight_mt', 'created_at', 'updated_at', 'created_by']
    inlines = [ChallanItemBatchMappingInline]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'notification_type', 'severity', 'status', 'title',
        'sent_at', 'acknowledged_at', 'resolved_at'
    ]
    list_filter = [
        'notification_type', 'severity', 'status',
        'sent_at', 'acknowledged_at', 'resolved_at'
    ]
    search_fields = [
        'title', 'message', 'order_in_transit__eway_bill_number',
        'loading_request__loading_request_id', 'crossover_record__crossover_id'
    ]
    readonly_fields = ['sent_at', 'created_at', 'updated_at', 'created_by']
    ordering = ['-sent_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('notification_type', 'severity', 'status', 'title', 'message')
        }),
        ('Related Records', {
            'fields': (
                'order_in_transit', 'inventory_batch',
                'loading_request', 'crossover_record'
            ),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': ('sent_at', 'acknowledged_at', 'resolved_at')
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        })
    )


class NotificationRecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0
    readonly_fields = ['delivered_at', 'read_at', 'acknowledged_at', 'created_at']


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = [
        'notification', 'user', 'delivery_status', 'delivery_channel',
        'delivered_at', 'read_at', 'acknowledged_at'
    ]
    list_filter = [
        'delivery_status', 'delivery_channel',
        'delivered_at', 'read_at', 'acknowledged_at'
    ]
    search_fields = [
        'notification__title', 'user__username',
        'delivery_address'
    ]
    readonly_fields = [
        'delivered_at', 'read_at', 'acknowledged_at',
        'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-created_at']

# Add inline to NotificationLog admin
NotificationLogAdmin.inlines = [NotificationRecipientInline]


class LedgerBatchMappingInline(admin.TabularInline):
    model = LedgerBatchMapping
    extra = 0
    readonly_fields = ['batch_balance_before', 'batch_balance_after', 'created_at', 'created_by']


@admin.register(GodownInventoryLedger)
class GodownInventoryLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'organization', 'transaction_type', 'godown', 'product',
        'inward_quantity', 'outward_quantity', 'balance_after_transaction',
        'entry_status', 'transaction_date'
    ]
    list_filter = [
        'organization', 'transaction_type', 'entry_status', 'godown', 'product',
        'transaction_date', 'is_system_generated', 'approval_required'
    ]
    search_fields = [
        'transaction_id', 'godown__name', 'product__name',
        'reference_document', 'transaction_notes'
    ]
    readonly_fields = [
        'transaction_id', 'balance_after_transaction', 'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-transaction_date', '-created_at']
    inlines = [LedgerBatchMappingInline]
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_id', 'transaction_type', 'transaction_date', 'entry_status')
        }),
        ('Location & Product', {
            'fields': ('godown', 'product')
        }),
        ('Quantities', {
            'fields': ('inward_quantity', 'outward_quantity', 'balance_after_transaction')
        }),
        ('Source Documents', {
            'fields': (
                'source_order_transit', 'source_loading_request',
                'source_crossover', 'source_challan'
            ),
            'classes': ('collapse',)
        }),
        ('Authorization', {
            'fields': ('authorized_by', 'approval_required', 'approved_at')
        }),
        ('Documentation', {
            'fields': ('reference_document', 'transaction_notes', 'quality_notes', 'condition_at_transaction')
        }),
        ('System Tracking', {
            'fields': ('is_system_generated', 'parent_transaction'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(LedgerBatchMapping)
class LedgerBatchMappingAdmin(admin.ModelAdmin):
    list_display = [
        'ledger_entry', 'inventory_batch', 'quantity_affected',
        'batch_balance_before', 'batch_balance_after'
    ]
    list_filter = [
        'ledger_entry__transaction_type', 'inventory_batch__godown',
        'inventory_batch__product'
    ]
    search_fields = [
        'ledger_entry__transaction_id', 'inventory_batch__batch_id'
    ]
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['inventory_batch__received_date']


@admin.register(GodownDailyBalance)
class GodownDailyBalanceAdmin(admin.ModelAdmin):
    list_display = [
        'balance_date', 'organization', 'godown', 'product', 'opening_balance',
        'total_inward', 'total_outward', 'closing_balance',
        'physical_count', 'variance_quantity', 'balance_status'
    ]
    list_filter = [
        'organization', 'balance_date', 'godown', 'product', 'balance_status',
        'count_verification_date', 'is_auto_calculated'
    ]
    search_fields = [
        'godown__name', 'product__name', 'count_verified_by__username',
        'verification_notes', 'discrepancy_reason'
    ]
    readonly_fields = [
        'closing_balance', 'variance_quantity', 'calculation_timestamp',
        'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-balance_date', 'godown__name', 'product__name']
    
    def get_variance_display(self, obj):
        """Display variance with color coding"""
        if obj.variance_quantity == 0:
            return "✅ No Variance"
        elif obj.variance_quantity > 0:
            return f"📈 Excess: +{obj.variance_quantity}"
        else:
            return f"📉 Shortage: {obj.variance_quantity}"
    
    get_variance_display.short_description = 'Variance'
    get_variance_display.admin_order_field = 'variance_quantity'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('balance_date', 'godown', 'product', 'balance_status')
        }),
        ('Calculated Balance', {
            'fields': ('opening_balance', 'total_inward', 'total_outward', 'closing_balance')
        }),
        ('Physical Verification', {
            'fields': (
                'physical_count', 'count_verified_by', 'count_verification_date',
                'variance_quantity'
            ),
            'classes': ('collapse',)
        }),
        ('Batch Analysis', {
            'fields': ('active_batches_count', 'oldest_batch_age_days'),
            'classes': ('collapse',)
        }),
        ('Quality Assessment', {
            'fields': ('good_condition_bags', 'damaged_bags', 'expired_bags'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': (
                'calculation_timestamp', 'last_transaction_id', 'is_auto_calculated'
            ),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('verification_notes', 'discrepancy_reason'),
            'classes': ('collapse',)
        })
    )


@admin.register(InventoryVariance)
class InventoryVarianceAdmin(admin.ModelAdmin):
    list_display = [
        'variance_id', 'organization', 'variance_type', 'godown', 'product',
        'variance_quantity', 'priority_level', 'status',
        'variance_date', 'get_variance_direction'
    ]
    list_filter = [
        'organization', 'variance_type', 'status', 'priority_level', 'godown', 'product',
        'variance_date', 'resolved_at'
    ]
    search_fields = [
        'variance_id', 'godown__name', 'product__name',
        'investigation_notes', 'root_cause', 'resolution_action'
    ]
    readonly_fields = [
        'variance_id', 'variance_quantity', 'investigation_started_at',
        'root_cause_identified_at', 'resolved_at', 'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-variance_date', '-created_at']
    
    def get_variance_direction(self, obj):
        """Display variance direction with color coding"""
        if obj.variance_quantity > 0:
            return f"📈 Excess: +{obj.variance_quantity}"
        elif obj.variance_quantity < 0:
            return f"📉 Shortage: {obj.variance_quantity}"
        else:
            return "⚖️ Balanced"
    
    get_variance_direction.short_description = 'Variance'
    get_variance_direction.admin_order_field = 'variance_quantity'
    
    def get_priority_display(self, obj):
        """Display priority with visual indicators"""
        priority_icons = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'CRITICAL': '🔴'
        }
        return f"{priority_icons.get(obj.priority_level, '')} {obj.get_priority_level_display()}"
    
    get_priority_display.short_description = 'Priority'
    get_priority_display.admin_order_field = 'priority_level'
    
    fieldsets = (
        ('Variance Information', {
            'fields': ('variance_id', 'variance_type', 'variance_date', 'status', 'priority_level')
        }),
        ('Location & Product', {
            'fields': ('godown', 'product', 'related_daily_balance')
        }),
        ('Quantities', {
            'fields': ('expected_quantity', 'actual_quantity', 'variance_quantity', 'estimated_value_impact')
        }),
        ('Investigation', {
            'fields': (
                'investigation_started_at', 'investigated_by', 'investigation_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Root Cause Analysis', {
            'fields': ('root_cause', 'root_cause_identified_at'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': (
                'resolution_action', 'resolved_at', 'resolved_by',
                'preventive_measures', 'adjustment_ledger_entry'
            ),
            'classes': ('collapse',)
        }),
        ('Escalation', {
            'fields': ('escalated_to', 'escalated_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )