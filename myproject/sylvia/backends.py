"""
Custom authentication backend with optimized profile loading
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileAwareAuthBackend(ModelBackend):
    """
    Custom authentication backend that eagerly loads user profile and organization.

    This reduces database queries in the middleware by pre-loading the profile
    relationship during authentication.
    """

    def get_user(self, user_id):
        """
        Override get_user to include select_related for profile and organization.
        This is called on every request for authenticated users.
        """
        try:
            user = User.objects.select_related('profile__organization').get(pk=user_id)
            return user
        except User.DoesNotExist:
            return None

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with profile pre-loading.
        """
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user:
            # Pre-load profile and organization
            try:
                # This loads the profile into cache
                _ = user.profile.organization
            except Exception:
                # Profile doesn't exist yet, that's ok
                pass
        return user
