from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Depot, Product, Dealer, Vehicle, Order, OrderItem, 
    MRN, Invoice, AuditLog, AppSettings, NotificationTemplate, DealerContext, OrderMRNImage
)

@admin.register(Depot)
class DepotAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'state', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'created_at']
    search_fields = ['name', 'code', 'city']
    ordering = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'unit', 'is_active', 'created_at']
    list_filter = ['is_active', 'unit', 'created_at']
    search_fields = ['name', 'code']
    ordering = ['name']

@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'phone', 'city', 'credit_limit', 'is_active']
    list_filter = ['is_active', 'city', 'state', 'created_at']
    search_fields = ['name', 'code', 'phone', 'contact_person']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'contact_person', 'phone', 'whatsapp_number', 'email')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'pincode')
        }),
        ('Business Details', {
            'fields': ('gstin', 'credit_limit', 'credit_days')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['truck_number', 'owner_name', 'driver_name', 'capacity', 'vehicle_type', 'is_active']
    list_filter = ['vehicle_type', 'is_active', 'created_at']
    search_fields = ['truck_number', 'owner_name', 'driver_name']
    ordering = ['truck_number']

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ['product', 'quantity', 'unit_price']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'dealer', 'vehicle', 'depot', 'status', 'order_date', 'total_quantity', 'whatsapp_sent']
    list_filter = ['status', 'depot', 'order_date', 'whatsapp_sent']
    search_fields = ['order_number', 'dealer__name', 'vehicle__truck_number']
    ordering = ['-order_date']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'dealer', 'vehicle', 'depot', 'order_date')
        }),
        ('Dates', {
            'fields': ('mrn_date', 'bill_date', 'dispatch_date', 'delivery_date')
        }),
        ('Status & Communication', {
            'fields': ('status', 'whatsapp_sent', 'whatsapp_sent_at', 'remarks')
        }),
        ('System Fields', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_quantity(self, obj):
        return f"{obj.get_total_quantity()} MT"
    total_quantity.short_description = "Total Qty"

@admin.register(MRN)
class MRNAdmin(admin.ModelAdmin):
    list_display = ['mrn_number', 'order', 'mrn_date', 'status', 'quality_checked']
    list_filter = ['status', 'quality_checked', 'mrn_date']
    search_fields = ['mrn_number', 'order__order_number', 'order__dealer__name']
    ordering = ['-mrn_date']
    readonly_fields = ['mrn_number']
    
    fieldsets = (
        ('MRN Information', {
            'fields': ('mrn_number', 'order', 'mrn_date', 'status')
        }),
        ('Quality Check', {
            'fields': ('quality_checked', 'quality_remarks', 'approved_by')
        }),
    )

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'order', 'invoice_date', 'due_date', 'total_amount', 'status', 'balance_amount']
    list_filter = ['status', 'invoice_date', 'due_date']
    search_fields = ['invoice_number', 'order__order_number', 'order__dealer__name']
    ordering = ['-invoice_date']
    readonly_fields = ['invoice_number', 'balance_amount']
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'order', 'invoice_date', 'due_date')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'status')
        }),
        ('Payment Information', {
            'fields': ('payment_received', 'payment_date', 'balance_amount')
        }),
    )
    
    def balance_amount(self, obj):
        balance = obj.get_balance_amount()
        if balance > 0:
            return format_html('<span style="color: red;">₹{}</span>', balance)
        return format_html('<span style="color: green;">₹{}</span>', balance)
    balance_amount.short_description = "Balance"



@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'model_name', 'object_id', 'user', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['object_id', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description']
    search_fields = ['key', 'description']
    ordering = ['key']

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active', 'created_at']
    list_filter = ['type', 'is_active', 'created_at']
    search_fields = ['name', 'subject']
    ordering = ['name']


@admin.register(OrderMRNImage)
class OrderMRNImageAdmin(admin.ModelAdmin):
    list_display = ['order',]
    search_fields = ['order__order_number']

@admin.register(DealerContext)
class DealerContextAdmin(admin.ModelAdmin):
    list_display = ['dealer', 'interaction_date', 'created_at']
    list_filter = ['interaction_date', 'created_at']
    search_fields = ['dealer__name', 'topics_discussed']
    ordering = ['-interaction_date']
    