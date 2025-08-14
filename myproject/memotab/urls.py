from django.urls import path, include

app_name = 'memotab'

urlpatterns = [
    # API routes
    path('api/', include('memotab.api_urls')),
]