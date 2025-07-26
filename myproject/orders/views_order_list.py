from django.shortcuts import render
from django.core.paginator import Paginator
from sylvia.models import Order

def order_list(request):
    orders = Order.objects.all().order_by('-order_date')
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'orders/order_list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages()
    })
