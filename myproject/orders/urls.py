from django.urls import path
from . import views
from .views_order_list import order_list
from .views import update_order, analytics, export_analytics, add_vehicle, edit_vehicle, vehicle_list, delete_vehicle, dealer_list, add_dealer, edit_dealer, delete_dealer, add_product, add_depot
from .views_dispatch_table import dispatch_table_upload, process_dispatch_image, confirm_dispatch_data, create_dispatch_orders

urlpatterns = [
    path('order-workflow/', views.order_workflow, name='order_workflow'),
    path('orders/', order_list, name='order_list'),
    path('update-order/<int:order_id>/', update_order, name='update_order'),
    path('analytics/', analytics, name='analytics'),
    path('export-analytics/', export_analytics, name='export_analytics'),
    
    # Vehicle management URLs
    path('vehicles/', vehicle_list, name='vehicle_list'),
    path('vehicles/add/', add_vehicle, name='add_vehicle'),
    path('vehicles/edit/<int:vehicle_id>/', edit_vehicle, name='edit_vehicle'),
    path('vehicles/delete/<int:vehicle_id>/', delete_vehicle, name='delete_vehicle'),
    
    # Dealer management URLs
    path('dealers/', dealer_list, name='dealer_list'),
    path('dealers/add/', add_dealer, name='add_dealer'),
    path('dealers/edit/<int:dealer_id>/', edit_dealer, name='edit_dealer'),
    path('dealers/delete/<int:dealer_id>/', delete_dealer, name='delete_dealer'),
    
    # Other entity management URLs (placeholders for future expansion)
    path('products/add/', add_product, name='add_product'),
    path('depots/add/', add_depot, name='add_depot'),
    
    # Dispatch table processing URLs
    path('dispatch-table/', dispatch_table_upload, name='dispatch_table_upload'),
    path('dispatch-table/process/', process_dispatch_image, name='process_dispatch_image'),
    path('dispatch-table/confirm/', confirm_dispatch_data, name='confirm_dispatch_data'),
    path('dispatch-table/create/', create_dispatch_orders, name='create_dispatch_orders'),
]
