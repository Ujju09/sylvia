from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .api_views import (
    DepotViewSet, ProductViewSet, DealerViewSet, VehicleViewSet,
    OrderViewSet, OrderItemViewSet, MRNViewSet, InvoiceViewSet,
    AuditLogViewSet, AppSettingsViewSet, NotificationTemplateViewSet,
    dashboard_stats, dealer_analytics, product_analytics, order_analytics,
    user_profile
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'depots', DepotViewSet)
router.register(r'products', ProductViewSet)
router.register(r'dealers', DealerViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'mrns', MRNViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'app-settings', AppSettingsViewSet)
router.register(r'notification-templates', NotificationTemplateViewSet)

urlpatterns = [
    # Authentication
    path('auth/login/', obtain_auth_token, name='api_token_auth'),
    path('auth/profile/', user_profile, name='user_profile'),
    
    # Analytics and Dashboard
    path('analytics/dashboard/', dashboard_stats, name='dashboard_stats'),
    path('analytics/dealers/', dealer_analytics, name='dealer_analytics'),
    path('analytics/products/', product_analytics, name='product_analytics'),
    path('analytics/orders/', order_analytics, name='order_analytics'),
    
    # Include all viewset routes
    path('', include(router.urls)),
]