"""
Custom model managers for automatic tenant filtering
"""
from django.db import models
from .middleware import get_current_organization


class TenantManager(models.Manager):
    """
    Manager that automatically filters querysets by current organization.

    This manager uses thread-local storage to get the current organization
    from the middleware and automatically filters all queries by it.

    Usage in models:
        class MyModel(TenantBaseModel):
            objects = TenantManager()  # Auto-filtered
            all_objects = models.Manager()  # Unfiltered for admin
    """

    def get_queryset(self):
        """Return queryset filtered by current organization"""
        queryset = super().get_queryset()
        organization = get_current_organization()

        # Only filter if we have an organization context
        if organization is not None:
            return queryset.filter(organization=organization)

        # No organization context - return unfiltered
        # (e.g., during migrations, management commands, or admin)
        return queryset

    def all_organizations(self):
        """
        Get queryset without tenant filter.

        Useful for admin interfaces or management commands
        that need to access data across all organizations.
        """
        return super().get_queryset()
