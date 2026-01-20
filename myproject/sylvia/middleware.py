"""
Tenant middleware for multi-tenancy support
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.shortcuts import redirect
import threading

# Thread-local storage for current organization
_thread_locals = threading.local()


def get_current_organization():
    """Get the current organization from thread-local storage"""
    return getattr(_thread_locals, 'organization', None)


def set_current_organization(organization):
    """Set the current organization in thread-local storage"""
    _thread_locals.organization = organization


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to inject tenant context into all requests.

    Extracts the organization from the authenticated user's profile
    and makes it available as request.organization.
    """

    # Paths that don't require organization context
    EXEMPT_URLS = ['/login/', '/logout/', '/admin/', '/api/v1/auth/']

    def process_request(self, request):
        """Process incoming request to add organization context"""
        # Check if URL is exempt
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return None

        # Only process for authenticated users
        if not request.user.is_authenticated:
            return None

        try:
            # Get organization from user profile
            # If using ProfileAwareAuthBackend, profile is already loaded via select_related
            # Otherwise, this will fetch it (with a query)
            if hasattr(request.user, 'profile'):
                organization = request.user.profile.organization
                request.organization = organization
                set_current_organization(organization)
            else:
                # User has no profile/organization
                return self._handle_no_organization(request)
        except Exception:
            # Handle any errors (e.g., UserProfile.DoesNotExist)
            return self._handle_no_organization(request)

        return None

    def _handle_no_organization(self, request):
        """Handle requests from users without an organization"""
        if request.path.startswith('/api/'):
            # Return 403 for API requests
            return JsonResponse({
                'error': 'User not associated with any organization',
                'detail': 'Please contact your administrator to assign you to an organization.'
            }, status=403)
        else:
            # Redirect to login for web requests with error message
            return redirect('/login/?error=no_organization')

    def process_response(self, request, response):
        """Clean up thread-local storage after request"""
        set_current_organization(None)
        return response
