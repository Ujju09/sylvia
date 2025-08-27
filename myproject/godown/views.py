from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json

from .models import OrderInTransit, GodownLocation, CrossoverRecord, GodownInventory
from .forms import OrderInTransitForm, CrossoverRecordForm
from sylvia.models import Product, Dealer


@login_required
def orderintransit_list(request):
    """List all OrderInTransit records with search and filtering"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    godown_filter = request.GET.get('godown', '')
    search_query = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all records
    orders = OrderInTransit.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if godown_filter:
        orders = orders.filter(godown_id=godown_filter)
    
    if search_query:
        orders = orders.filter(
            Q(eway_bill_number__icontains=search_query) |
            Q(transport_document_number__icontains=search_query) |
            Q(dispatch_id__icontains=search_query)
        )
    
    if date_from:
        orders = orders.filter(actual_arrival_date__date__gte=date_from)
    
    if date_to:
        orders = orders.filter(actual_arrival_date__date__lte=date_to)
    
    # Calculate summary statistics
    summary_stats = orders.aggregate(
        total_records=Count('dispatch_id'),
        total_expected_bags=Sum('expected_total_bags'),
        total_received_bags=Sum('actual_received_bags'),
        total_good_bags=Sum('good_bags'),
        total_damaged_bags=Sum('damaged_bags'),
        total_shortage_bags=Sum('shortage_bags'),
        total_excess_bags=Sum('excess_bags')
    )
    
    # Status counts for dashboard
    status_counts = OrderInTransit.objects.values('status').annotate(
        count=Count('dispatch_id')
    ).order_by('status')
    
    # Pagination
    paginator = Paginator(orders, 20)  # Show 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get godown choices for filter dropdown
    godown_choices = GodownLocation.objects.filter(is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'godown_filter': godown_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'summary_stats': summary_stats,
        'status_counts': list(status_counts),
        'godown_choices': godown_choices,
        'status_choices': OrderInTransit.TRANSIT_STATUS_CHOICES
    }
    
    return render(request, 'godown/orderintransit/list.html', context)


@login_required
def orderintransit_detail(request, dispatch_id):
    """Display detailed view of a specific OrderInTransit record"""
    
    order = get_object_or_404(OrderInTransit, dispatch_id=dispatch_id)
    
    # Calculate additional metrics
    storage_bags = order.get_storage_bags()
    discrepancy = order.expected_total_bags - order.actual_received_bags
    discrepancy_percentage = 0
    if order.expected_total_bags > 0:
        discrepancy_percentage = abs(discrepancy) / order.expected_total_bags * 100
    
    context = {
        'order': order,
        'storage_bags': storage_bags,
        'discrepancy': discrepancy,
        'discrepancy_percentage': round(discrepancy_percentage, 2),
    }
    
    return render(request, 'godown/orderintransit/detail.html', context)


@login_required
def orderintransit_create(request):
    """Create a new OrderInTransit record"""
    
    if request.method == 'POST':
        form = OrderInTransitForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            
            messages.success(
                request, 
                f'Order in Transit "{order.eway_bill_number}" has been created successfully!'
            )
            return redirect('orderintransit_detail', dispatch_id=order.dispatch_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = OrderInTransitForm()
    
    context = {
        'form': form,
        'title': 'Create New Order in Transit',
        'submit_text': 'Create Order'
    }
    
    return render(request, 'godown/orderintransit/form.html', context)


@login_required
def orderintransit_update(request, dispatch_id):
    """Update an existing OrderInTransit record"""
    
    order = get_object_or_404(OrderInTransit, dispatch_id=dispatch_id)
    
    if request.method == 'POST':
        form = OrderInTransitForm(request.POST, instance=order)
        if form.is_valid():
            updated_order = form.save(commit=False)
            updated_order.updated_at = timezone.now()
            updated_order.save()
            
            messages.success(
                request, 
                f'Order in Transit "{updated_order.eway_bill_number}" has been updated successfully!'
            )
            return redirect('orderintransit_detail', dispatch_id=updated_order.dispatch_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = OrderInTransitForm(instance=order)
    
    context = {
        'form': form,
        'order': order,
        'title': f'Update Order in Transit - {order.eway_bill_number}',
        'submit_text': 'Update Order'
    }
    
    return render(request, 'godown/orderintransit/form.html', context)


@login_required
@csrf_exempt
def orderintransit_calculate_quantities(request):
    """AJAX endpoint to calculate shortage/excess bags"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            expected_total = int(data.get('expected_total', 0))
            actual_received = int(data.get('actual_received', 0))
            
            # Calculate shortage and excess
            shortage_bags = 0
            excess_bags = 0
            
            if expected_total > actual_received:
                shortage_bags = expected_total - actual_received
            elif actual_received > expected_total:
                excess_bags = actual_received - expected_total
            
            return JsonResponse({
                'success': True,
                'shortage_bags': shortage_bags,
                'excess_bags': excess_bags,
                'discrepancy': expected_total - actual_received,
                'discrepancy_percentage': round(abs(expected_total - actual_received) / expected_total * 100, 2) if expected_total > 0 else 0
            })
            
        except (ValueError, json.JSONDecodeError) as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@csrf_exempt
def orderintransit_validate_bags(request):
    """AJAX endpoint to validate bag quantities"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            actual_received = int(data.get('actual_received', 0))
            good_bags = int(data.get('good_bags', 0))
            damaged_bags = int(data.get('damaged_bags', 0))
            crossover_bags = int(data.get('crossover_bags', 0))
            
            errors = []
            
            # Check if good + damaged equals actual received
            total_accounted = good_bags + damaged_bags
            if total_accounted != actual_received:
                errors.append(f"Good bags ({good_bags}) + Damaged bags ({damaged_bags}) = {total_accounted}, but you received {actual_received} bags")
            
            # Check if crossover bags exceed good bags
            if crossover_bags > good_bags:
                errors.append(f"Crossover bags ({crossover_bags}) cannot exceed good bags ({good_bags})")
            
            # Calculate storage bags
            storage_bags = good_bags - crossover_bags
            
            return JsonResponse({
                'success': len(errors) == 0,
                'errors': errors,
                'storage_bags': storage_bags,
                'total_accounted': total_accounted
            })
            
        except (ValueError, json.JSONDecodeError) as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def orderintransit_dashboard(request):
    """Dashboard view with key metrics and recent orders"""
    
    # Key metrics
    total_orders = OrderInTransit.objects.count()
    in_transit_count = OrderInTransit.objects.filter(status='IN_TRANSIT').count()
    arrived_count = OrderInTransit.objects.filter(status='ARRIVED').count()
    
    # Today's arrivals
    today = timezone.now().date()
    today_arrivals = OrderInTransit.objects.filter(
        actual_arrival_date__date=today
    ).count()
    
    # Weekly metrics
    week_ago = today - timezone.timedelta(days=7)
    weekly_stats = OrderInTransit.objects.filter(
        created_at__date__gte=week_ago
    ).aggregate(
        total_expected=Sum('expected_total_bags'),
        total_received=Sum('actual_received_bags'),
        total_good=Sum('good_bags'),
        total_damaged=Sum('damaged_bags')
    )
    
    # Recent orders (last 10)
    recent_orders = OrderInTransit.objects.order_by('-created_at')[:10]
    
    # Orders by godown
    orders_by_godown = OrderInTransit.objects.values(
        'godown__name', 'godown__code'
    ).annotate(
        count=Count('dispatch_id'),
        total_bags=Sum('actual_received_bags')
    ).order_by('-count')
    
    context = {
        'total_orders': total_orders,
        'in_transit_count': in_transit_count,
        'arrived_count': arrived_count,
        'today_arrivals': today_arrivals,
        'weekly_stats': weekly_stats,
        'recent_orders': recent_orders,
        'orders_by_godown': list(orders_by_godown),
    }
    
    return render(request, 'godown/orderintransit/dashboard.html', context)


# =============================================================================
# CROSSOVER RECORD VIEWS
# =============================================================================

@login_required
def crossover_list(request):
    """List all CrossoverRecord records with search and filtering"""
    
    # Get filter parameters
    dealer_filter = request.GET.get('dealer', '')
    product_filter = request.GET.get('product', '')
    search_query = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all records
    crossovers = CrossoverRecord.objects.select_related(
        'source_order_transit', 'destination_dealer', 'product', 'supervised_by'
    ).order_by('-approved_date')
    
    # Apply filters
    if dealer_filter:
        crossovers = crossovers.filter(destination_dealer_id=dealer_filter)
    
    if product_filter:
        crossovers = crossovers.filter(product_id=product_filter)
    
    if search_query:
        crossovers = crossovers.filter(
            Q(crossover_id__icontains=search_query) |
            Q(destination_dealer__name__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(source_order_transit__eway_bill_number__icontains=search_query)
        )
    
    if date_from:
        crossovers = crossovers.filter(approved_date__date__gte=date_from)
    
    if date_to:
        crossovers = crossovers.filter(approved_date__date__lte=date_to)
    
    # Calculate summary statistics
    summary_stats = crossovers.aggregate(
        total_records=Count('crossover_id'),
        total_requested_bags=Sum('requested_bags'),
        total_transferred_bags=Sum('actual_transferred_bags'),
    )
    
    # Get unique dealers and products for filter dropdowns
    dealer_choices = Dealer.objects.filter(is_active=True).order_by('name')
    product_choices = Product.objects.filter(is_active=True).order_by('name')
    
    # Pagination
    paginator = Paginator(crossovers, 20)  # Show 20 crossovers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'dealer_filter': dealer_filter,
        'product_filter': product_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'summary_stats': summary_stats,
        'dealer_choices': dealer_choices,
        'product_choices': product_choices,
    }
    
    return render(request, 'godown/crossover/list.html', context)


@login_required
def crossover_detail(request, crossover_id):
    """Display detailed view of a specific CrossoverRecord"""
    
    crossover = get_object_or_404(CrossoverRecord, crossover_id=crossover_id)
    
    # Calculate metrics
    completion_percentage = 0
    if crossover.requested_bags > 0:
        completion_percentage = (crossover.actual_transferred_bags / crossover.requested_bags) * 100
    
    # Get related crossover records (same source order)
    related_crossovers = CrossoverRecord.objects.filter(
        source_order_transit=crossover.source_order_transit
    ).exclude(crossover_id=crossover_id).select_related(
        'destination_dealer', 'product'
    )
    
    context = {
        'crossover': crossover,
        'completion_percentage': round(completion_percentage, 1),
        'related_crossovers': related_crossovers,
    }
    
    return render(request, 'godown/crossover/detail.html', context)


@login_required
def crossover_create(request):
    """Create a new CrossoverRecord using simplified single-product workflow"""
    
    if request.method == 'POST':
        form = CrossoverRecordForm(request.POST)
        
        if form.is_valid():
            try:
                # Create single CrossoverRecord instance
                crossover = form.save(commit=False)
                crossover.created_by = request.user
                crossover.save()
                
                messages.success(
                    request,
                    f'Successfully created crossover record "{crossover.crossover_id}" for '
                    f'{crossover.destination_dealer.name}!'
                )
                
                return redirect('crossover_detail', crossover_id=crossover.crossover_id)
                    
            except Exception as e:
                messages.error(request, f'Error creating crossover record: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CrossoverRecordForm()
    
    context = {
        'form': form,
        'title': 'Create New Crossover Record',
        'submit_text': 'Create Crossover'
    }
    
    return render(request, 'godown/crossover/form.html', context)


@login_required
def crossover_update(request, crossover_id):
    """Update an existing CrossoverRecord"""
    
    crossover = get_object_or_404(CrossoverRecord, crossover_id=crossover_id)
    
    if request.method == 'POST':
        form = CrossoverRecordForm(request.POST, instance=crossover)
        if form.is_valid():
            updated_crossover = form.save(commit=False)
            updated_crossover.updated_at = timezone.now()
            updated_crossover.save()
            
            messages.success(
                request,
                f'Crossover record "{updated_crossover.crossover_id}" has been updated successfully!'
            )
            return redirect('crossover_detail', crossover_id=updated_crossover.crossover_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CrossoverRecordForm(instance=crossover)
    
    context = {
        'form': form,
        'crossover': crossover,
        'title': f'Update Crossover Record - {crossover.crossover_id}',
        'submit_text': 'Update Crossover'
    }
    
    return render(request, 'godown/crossover/form.html', context)


# =============================================================================
# AJAX ENDPOINTS FOR CROSSOVER
# =============================================================================

@login_required
@csrf_exempt
def get_available_bags(request):
    """AJAX endpoint to get available bags for a specific product in a transit order"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            source_order_id = data.get('source_order_transit_id')
            product_id = data.get('product_id')
            
            if not source_order_id or not product_id:
                return JsonResponse({'success': False, 'error': 'Source order and product are required'})
            
            # Get available bags for the specific product in the transit order
            available_inventory = OrderInTransit.objects.filter(
                dispatch_id=source_order_id,
                product_id=product_id,
                good_bags__gt=0
            ).aggregate(
                total_available=Sum('good_bags')
            )
            
            available_bags = available_inventory['total_available'] or 0
            
            return JsonResponse({
                'success': True,
                'available_bags': available_bags
            })
            
        except (ValueError, json.JSONDecodeError) as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
