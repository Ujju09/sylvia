"""
Custom permissions for tenant-aware access control
"""
from rest_framework.permissions import BasePermission


class IsTenantUser(BasePermission):
    """
    Permission class that ensures user belongs to an organization
    and can only access their organization's data.

    - Checks that user is authenticated
    - Checks that user has an organization
    - For object-level permissions, verifies the object belongs to user's organization
    - Superusers bypass all checks
    """

    def has_permission(self, request, view):
        """Check if user has permission to access the view"""
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have an organization (added by TenantMiddleware)
        if not hasattr(request, 'organization') or request.organization is None:
            return False

        return True

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access this specific object"""
        # Superusers can access everything
        if request.user.is_superuser:
            return True

        # If object doesn't have organization attribute, allow access
        # (e.g., for models that aren't tenant-specific)
        if not hasattr(obj, 'organization'):
            return True

        # Check if object belongs to user's organization
        return obj.organization == request.organization
