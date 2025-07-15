from django.urls import path
from . import views
from .views_order_list import order_list
from .views import update_order, analytics, export_analytics, add_vehicle, edit_vehicle, vehicle_list, delete_vehicle, add_dealer, add_product, add_depot

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
    
    # Other entity management URLs (placeholders for future expansion)
    path('dealers/add/', add_dealer, name='add_dealer'),
    path('products/add/', add_product, name='add_product'),
    path('depots/add/', add_depot, name='add_depot'),
]
