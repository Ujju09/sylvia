from django.urls import path
from . import views

urlpatterns = [
    # Godown Home - Main dashboard
    path('', views.godown_home, name='godown_home'),
    path('<int:godown_id>/', views.godown_detail, name='godown_detail'),
    
    # OrderInTransit URLs
    path('transit/', views.orderintransit_list, name='orderintransit_list'),
    path('transit/create/', views.orderintransit_create, name='orderintransit_create'),
    path('transit/<str:dispatch_id>/', views.orderintransit_detail, name='orderintransit_detail'),
    path('transit/<str:dispatch_id>/edit/', views.orderintransit_update, name='orderintransit_update'),
    path('transit/dashboard/', views.orderintransit_dashboard, name='orderintransit_dashboard'),
    
    # AJAX endpoints for OrderInTransit
    path('ajax/transit/calculate-quantities/', views.orderintransit_calculate_quantities, name='orderintransit_calculate_quantities'),
    path('ajax/transit/validate-bags/', views.orderintransit_validate_bags, name='orderintransit_validate_bags'),
    
    # CrossoverRecord URLs
    path('crossover/', views.crossover_list, name='crossover_list'),
    path('crossover/create/', views.crossover_create, name='crossover_create'),
    path('crossover/<str:crossover_id>/', views.crossover_detail, name='crossover_detail'),
    path('crossover/<str:crossover_id>/edit/', views.crossover_update, name='crossover_update'),
    
    # AJAX endpoints for Crossover
    path('ajax/crossover/available-bags/', views.get_available_bags, name='get_available_bags'),


    
    # Godown Inventory
    path('inventory/', views.godown_inventory_list, name='godown_inventory_list'),
    path('inventory/dashboard/', views.godown_inventory_dashboard, name='godown_inventory_dashboard'),
    path('inventory/create/', views.godown_inventory_create, name='godown_inventory_create'),
    path('inventory/<str:batch_id>/', views.godown_inventory_detail, name='godown_inventory_detail'),
    path('inventory/<str:batch_id>/edit/', views.godown_inventory_update, name='godown_inventory_update'),
    
    # Loading Records - Simple URLs for easy access
    path('loading/', views.loading_record_list, name='loading_record_list'),
    path('loading/new/', views.loading_record_create, name='loading_record_create'),
    path('loading/<str:loading_request_id>/', views.loading_record_detail, name='loading_record_detail'),
    path('loading/<str:loading_request_id>/edit/', views.loading_record_update, name='loading_record_update'),
    path('loading/dashboard/', views.loading_record_dashboard, name='loading_record_dashboard'),

    # Audit Checklist PDF Generation
    path('audit-pdf/<int:godown_id>/', views.generate_audit_pdf, name='generate_audit_pdf'),

    # Opening Stock Image Sharing
    path('share-opening-stock/', views.share_opening_stock_image, name='share_opening_stock_image'),
]