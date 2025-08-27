from django.urls import path
from . import views

urlpatterns = [
    # OrderInTransit URLs
    path('transit/', views.orderintransit_list, name='orderintransit_list'),
    path('transit/create/', views.orderintransit_create, name='orderintransit_create'),
    path('transit/<str:dispatch_id>/', views.orderintransit_detail, name='orderintransit_detail'),
    path('transit/<str:dispatch_id>/edit/', views.orderintransit_update, name='orderintransit_update'),
    path('transit/dashboard/', views.orderintransit_dashboard, name='orderintransit_dashboard'),
    
    # AJAX endpoints for OrderInTransit
    path('ajax/transit/calculate-quantities/', views.orderintransit_calculate_quantities, name='orderintransit_calculate_quantities'),
    path('ajax/transit/validate-bags/', views.orderintransit_validate_bags, name='orderintransit_validate_bags'),
    
    # CrossoverRecord URLs
    path('crossover/', views.crossover_list, name='crossover_list'),
    path('crossover/create/', views.crossover_create, name='crossover_create'),
    path('crossover/<str:crossover_id>/', views.crossover_detail, name='crossover_detail'),
    path('crossover/<str:crossover_id>/edit/', views.crossover_update, name='crossover_update'),
    
    # AJAX endpoints for Crossover
    path('ajax/crossover/available-bags/', views.get_available_bags, name='get_available_bags'),
]