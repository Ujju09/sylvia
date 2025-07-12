from django.urls import path
from . import views
from .views_order_list import order_list
from .views import update_order, analytics, export_analytics

urlpatterns = [
    path('order-workflow/', views.order_workflow, name='order_workflow'),
    path('orders/', order_list, name='order_list'),
    path('update-order/<int:order_id>/', update_order, name='update_order'),
    path('analytics/', analytics, name='analytics'),
    path('export-analytics/', export_analytics, name='export_analytics'),
]
