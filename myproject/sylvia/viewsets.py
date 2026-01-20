"""
Base viewsets with automatic tenant filtering
"""
from rest_framework import viewsets
from .permissions import IsTenantUser


class TenantViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet with automatic tenant filtering and permissions.

    Features:
    - Automatically filters querysets by current organization
    - Auto-sets organization when creating objects
    - Auto-sets created_by to current user
    - Enforces IsTenantUser permission

    Usage:
        class DealerViewSet(TenantViewSet):
            queryset = Dealer.objects.all()
            serializer_class = DealerSerializer
    """

    permission_classes = [IsTenantUser]

    def get_queryset(self):
        """Filter queryset by current organization"""
        queryset = super().get_queryset()

        # Check if model has organization field
        if hasattr(queryset.model, 'organization'):
            # Filter by current organization
            return queryset.filter(organization=self.request.organization)

        # Model doesn't have organization field, return unfiltered
        return queryset

    def perform_create(self, serializer):
        """Auto-set organization and created_by when creating objects"""
        # Build save kwargs
        save_kwargs = {}

        # Set organization if model has the field
        if hasattr(serializer.Meta.model, 'organization'):
            save_kwargs['organization'] = self.request.organization

        # Set created_by if model has the field
        if hasattr(serializer.Meta.model, 'created_by'):
            save_kwargs['created_by'] = self.request.user

        # Save with auto-populated fields
        serializer.save(**save_kwargs)
