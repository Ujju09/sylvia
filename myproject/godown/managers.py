"""
Custom model manager for automatic tenant filtering in the godown app.
Reuses the organization context set by sylvia.middleware.TenantMiddleware.
"""
from django.db import models
from sylvia.middleware import get_current_organization


class GodownTenantManager(models.Manager):
    """
    Manager that automatically filters querysets by current organization.

    Uses the same thread-local organization context set by sylvia's TenantMiddleware.
    No separate middleware is needed — sylvia.middleware.TenantMiddleware is already active.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        organization = get_current_organization()
        if organization is not None:
            return queryset.filter(organization=organization)
        return queryset
