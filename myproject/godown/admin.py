from django.contrib import admin
from .models import (
    GodownLocation, OrderInTransit, GodownInventory, CrossoverRecord,
    LoadingRequest, DeliveryChallan, DeliveryChallanItem, ChallanItemBatchMapping,
    NotificationLog, NotificationRecipient
)


@admin.register(GodownLocation)
class GodownLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'state', 'manager', 'is_active', 'created_at']
    list_filter = ['is_active', 'city', 'state', 'created_at']
    search_fields = ['name', 'code', 'city', 'address']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['name']


@admin.register(OrderInTransit)
class OrderInTransitAdmin(admin.ModelAdmin):
    list_display = [
        'eway_bill_number', 'dispatch_id', 'status', 'godown', 'actual_arrival_date','product',
        'expected_total_bags', 'actual_received_bags', 'good_bags'
    ]
    list_filter = [
        'status', 'godown', 'crossover_required', 'actual_arrival_date'
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
        'batch_id', 'godown', 'product', 'status',
        'good_bags_available', 'good_bags_reserved', 'damaged_bags',
        'received_date', 'quality_grade'
    ]
    list_filter = [
        'status', 'godown', 'product', 'quality_grade',
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
        'crossover_id', 'destination_dealer', 'product', 
        'requested_bags', 'actual_transferred_bags',
    ]
    list_filter = [
       'destination_dealer', 'product',
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
        'loading_request_id', 'dealer', 'vehicle', 'product', 'status', 'priority',
        'requested_bags', 'allocated_bags', 'loaded_bags',
        'requested_date', 'required_by_date'
    ]
    list_filter = [
        'status', 'priority', 'godown', 'product', 'dealer',
        'requested_date', 'required_by_date'
    ]
    search_fields = [
        'loading_request_id', 'dealer__name', 'vehicle__truck_number',
        'product__name', 'special_instructions'
    ]
    readonly_fields = [
        'loading_request_id', 'requested_date', 'created_at', 'updated_at', 'created_by'
    ]
    ordering = ['-requested_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('loading_request_id', 'godown', 'status', 'priority')
        }),
        ('Request Details', {
            'fields': ('dealer', 'vehicle', 'product')
        }),
        ('Quantities', {
            'fields': ('requested_bags', 'allocated_bags', 'loaded_bags')
        }),
        ('Timeline', {
            'fields': (
                'requested_date', 'required_by_date', 'approved_date',
                'loading_start_time', 'loading_completion_time'
            )
        }),
        ('Authorization', {
            'fields': ('requested_by', 'approved_by', 'supervised_by')
        }),
        ('Instructions & Notes', {
            'fields': ('special_instructions', 'loading_notes'),
            'classes': ('collapse',)
        })
    )


@admin.register(DeliveryChallan)
class DeliveryChallanAdmin(admin.ModelAdmin):
    list_display = [
        'challan_number', 'challan_type', 'dealer', 'vehicle', 'status',
        'total_bags', 'total_weight_mt', 'issue_date'
    ]
    list_filter = [
        'challan_type', 'status', 'godown', 'dealer',
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