from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import date
from sylvia.models import Order, Dealer

def order_list(request):
    # Get all orders first for statistics calculation
    all_orders = Order.objects.all()
    
    # Calculate order statistics by status
    today = date.today()
    order_stats = all_orders.aggregate(
        total_orders=Count('id'),
        pending_orders=Count('id', filter=Q(status='PENDING')),
        anonymous_dealers_count=Count('dealer_id', filter=Q(dealer__name__iexact='anonymous')),
        mrn_created_orders=Count('id', filter=Q(mrn_date=today)),
        billed_orders=Count('id', filter=Q(status='BILLED'))
    )
    
    # Start with all orders for filtering
    orders = all_orders.order_by('-order_date')
    
    # Search and filtering
    search_query = request.GET.get('search', '')
    dealer_filter = request.GET.get('dealer', '')
    status_filter = request.GET.get('status', '')
    
    # Apply dealer filter
    if dealer_filter:
        try:
            dealer_id = int(dealer_filter)
            if Dealer.objects.filter(id=dealer_id, is_active=True).exists():
                orders = orders.filter(dealer_id=dealer_id)
        except (ValueError, TypeError):
            pass
    
    # Apply status filter
    if status_filter and status_filter != 'ALL':
        orders = orders.filter(status=status_filter)
    
    # Apply search query (search in dealer name, order number, vehicle number)
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(dealer__name__icontains=search_query) |
            Q(dealer__code__icontains=search_query) |
            Q(vehicle__truck_number__icontains=search_query)
        )
    
    # Get all active dealers for the dropdown
    dealers = Dealer.objects.filter(is_active=True).order_by('name')
    
    # Order status choices for the dropdown
    order_status_choices = Order.ORDER_STATUS_CHOICES
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'orders/order_list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'order_stats': order_stats,
        'dealers': dealers,
        'order_status_choices': order_status_choices,
        'search_query': search_query,
        'dealer_filter': dealer_filter,
        'status_filter': status_filter,
    })
