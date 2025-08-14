from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .api_views import SourceViewSet, CashCollectViewSet, UserViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'cash-collections', CashCollectViewSet, basename='cashcollect')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    # Authentication (shared with main app)
    path('auth/login/', obtain_auth_token, name='memotab_token_auth'),
    
    # Include all viewset routes
    path('', include(router.urls)),
]