from django.contrib import admin
from .models import Source, CashCollect


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['text', 'is_active', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at']
    search_fields = ['text']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['text']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when creating
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CashCollect)
class CashCollectAdmin(admin.ModelAdmin):
    list_display = ['date', 'source', 'amount', 'received_by', 'created_at']
    list_filter = ['date', 'source', 'received_by', 'created_at']
    search_fields = ['note', 'source__text', 'received_by__username']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    ordering = ['-date', '-created_at']
    raw_id_fields = ['source', 'received_by']
    
    fieldsets = (
        ('Collection Details', {
            'fields': ['date', 'source', 'amount', 'received_by']
        }),
        ('Additional Information', {
            'fields': ['note']
        }),
        ('System Information', {
            'fields': ['created_at', 'updated_at', 'created_by'],
            'classes': ['collapse']
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when creating
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
