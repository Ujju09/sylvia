from django.shortcuts import render
from sylvia.models import Order

def order_list(request):
    orders = Order.objects.all().order_by('-order_date')
    return render(request, 'orders/order_list.html', {'orders': orders})
