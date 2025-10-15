from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .api_views import (
    DepotViewSet, ProductViewSet, DealerViewSet, VehicleViewSet,
    OrderViewSet, OrderItemViewSet, OrderMRNImageViewSet, MRNViewSet,
    AuditLogViewSet, AppSettingsViewSet, NotificationTemplateViewSet,
    DealerContextViewSet, dashboard_stats, dealer_analytics, product_analytics, 
    order_analytics, user_profile
)

# Import BI Views
from .bi_views import (
    executive_summary, stock_analytics, monthly_trends, 
    depot_analytics, operations_live
)

# Import MemoTab ViewSets
from memotab.api_views import SourceViewSet, CashCollectViewSet
from memotab.api_views import UserViewSet as MemoTabUserViewSet

# Import Godown ViewSets
from godown.api_views import LoadingRequestImageViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'depots', DepotViewSet)
router.register(r'products', ProductViewSet)
router.register(r'dealers', DealerViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'mrn-images', OrderMRNImageViewSet)
router.register(r'mrns', MRNViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'app-settings', AppSettingsViewSet)
router.register(r'notification-templates', NotificationTemplateViewSet)
router.register(r'dealer-context', DealerContextViewSet)

# MemoTab ViewSets
router.register(r'memotab/sources', SourceViewSet, basename='memotab-source')
router.register(r'memotab/cash-collections', CashCollectViewSet, basename='memotab-cashcollect')
router.register(r'memotab/users', MemoTabUserViewSet, basename='memotab-user')

# Godown ViewSets
router.register(r'loading-request-images', LoadingRequestImageViewSet, basename='loadingrequestimage')

urlpatterns = [
    # Authentication
    path('auth/login/', obtain_auth_token, name='api_token_auth'),
    path('auth/profile/', user_profile, name='user_profile'),
    
    # Analytics and Dashboard (Legacy)
    path('analytics/dashboard/', dashboard_stats, name='dashboard_stats'),
    path('analytics/dealers/', dealer_analytics, name='dealer_analytics'),
    path('analytics/products/', product_analytics, name='product_analytics'),
    path('analytics/orders/', order_analytics, name='order_analytics'),
    
    # Business Intelligence APIs
    path('bi/executive-summary/', executive_summary, name='bi_executive_summary'),
    path('bi/stock-analytics/', stock_analytics, name='bi_stock_analytics'),
    path('bi/monthly-trends/', monthly_trends, name='bi_monthly_trends'),
    path('bi/depot-analytics/', depot_analytics, name='bi_depot_analytics'),
    path('bi/operations-live/', operations_live, name='bi_operations_live'),
    
    # Include all viewset routes
    path('', include(router.urls)),
]