"""
Context processors for making organization data available in templates
"""


def organization_context(request):
    """
    Add user's organization to template context.

    Makes the user's organization available in all templates
    as {{ user_organization }}.
    """
    context = {}

    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile:
            context['user_organization'] = request.user.profile.organization
        else:
            context['user_organization'] = None

    return context
