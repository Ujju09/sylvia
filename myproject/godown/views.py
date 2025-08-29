from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json

from .models import OrderInTransit, GodownLocation, CrossoverRecord, GodownInventory, LoadingRequest
from .forms import OrderInTransitForm, CrossoverRecordForm, GodownInventoryForm, LoadingRecordForm
from sylvia.models import Product, Dealer


@login_required
def godown_home(request):
    """
    Main dashboard view for godown operations with comprehensive statistics and quick access links
    """
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    
    # Quick overview statistics
    total_orders_in_transit = OrderInTransit.objects.count()
    arrived_today = OrderInTransit.objects.filter(
        status='ARRIVED',
        actual_arrival_date__date=today
    ).count()
    
    pending_in_transit = OrderInTransit.objects.filter(status='IN_TRANSIT').count()
    
    # Inventory summary
    active_inventory = GodownInventory.objects.filter(status='ACTIVE')
    total_available_bags = active_inventory.aggregate(
        total=Sum('good_bags_available')
    )['total'] or 0
    
    total_reserved_bags = active_inventory.aggregate(
        total=Sum('good_bags_reserved')
    )['total'] or 0
    
    # Low stock products (less than 50 bags available)
    low_stock_products = active_inventory.values(
        'product__name', 'product__code'
    ).annotate(
        total_bags=Sum('good_bags_available')
    ).filter(total_bags__lt=50).count()
    
    # Recent loading activities
    recent_loading_requests = LoadingRequest.objects.select_related(
        'dealer', 'product', 'godown'
    ).order_by('-created_at')[:8]
    
    # Today's loading statistics
    today_loadings = LoadingRequest.objects.filter(created_at__date=today)
    today_loading_count = today_loadings.count()
    today_bags_requested = today_loadings.aggregate(
        total=Sum('requested_bags')
    )['total'] or 0
    today_bags_loaded = today_loadings.aggregate(
        total=Sum('loaded_bags')
    )['total'] or 0
    
    # Crossover activities this week
    recent_crossovers = CrossoverRecord.objects.select_related(
        'destination_dealer', 'product', 'source_order_transit'
    ).filter(created_at__date__gte=week_ago).order_by('-created_at')[:5]
    
    weekly_crossovers_count = CrossoverRecord.objects.filter(
        created_at__date__gte=week_ago
    ).count()
    
    # Recent orders in transit
    recent_transit_orders = OrderInTransit.objects.select_related(
        'godown', 'product'
    ).order_by('-created_at')[:5]
    
    # Godown-wise inventory summary
    godown_summaries = active_inventory.values(
        'godown__name', 'godown__code'
    ).annotate(
        total_bags=Sum('good_bags_available'),
        total_products=Count('product', distinct=True)
    ).filter(total_bags__gt=0).order_by('-total_bags')[:5]
    
    # Critical alerts
    critical_alerts = []
    
    # Add low stock alerts
    if low_stock_products > 0:
        critical_alerts.append({
            'type': 'warning',
            'message': f'{low_stock_products} product(s) have low stock (< 50 bags)',
            'action': 'Check Inventory',
            'url': '/godown/inventory/'
        })
    
    # Add pending transit orders
    if pending_in_transit > 5:
        critical_alerts.append({
            'type': 'info',
            'message': f'{pending_in_transit} orders are currently in transit',
            'action': 'View Transit Orders',
            'url': '/godown/transit/'
        })
    
    context = {
        'total_orders_in_transit': total_orders_in_transit,
        'arrived_today': arrived_today,
        'pending_in_transit': pending_in_transit,
        'total_available_bags': total_available_bags,
        'total_reserved_bags': total_reserved_bags,
        'low_stock_products': low_stock_products,
        'recent_loading_requests': recent_loading_requests,
        'today_loading_count': today_loading_count,
        'today_bags_requested': today_bags_requested,
        'today_bags_loaded': today_bags_loaded,
        'recent_crossovers': recent_crossovers,
        'weekly_crossovers_count': weekly_crossovers_count,
        'recent_transit_orders': recent_transit_orders,
        'godown_summaries': godown_summaries,
        'critical_alerts': critical_alerts,
        'today_date': today,
    }
    
    return render(request, 'godown/home.html', context)


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
        form = OrderInTransitForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save()  # This will trigger the atomic transaction with all related records
            
            messages.success(
                request, 
                f'Order in Transit "{order.eway_bill_number}" has been created successfully! '
                f'Related inventory and crossover records have been created automatically.'
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
        form = OrderInTransitForm(request.POST, instance=order, user=request.user)
        if form.is_valid():
            updated_order = form.save()  # Form handles the save logic, won't create duplicates for updates
            
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



# =============================================================================
# GodownInventory VIEWS
# =============================================================================


@login_required
def godown_inventory_dashboard(request):
    """Dashboard view with inventory summaries"""
    
    # Get all active inventory
    active_inventory = GodownInventory.objects.filter(status='ACTIVE')
    
    # Product-wise inventory summary (only show products with available stock)
    product_summaries = active_inventory.values(
        'product__name', 'product__code'
    ).annotate(
        total_bags=Sum('good_bags_available'),
        total_batches=Count('batch_id'),
        total_godowns=Count('godown', distinct=True)
    ).filter(total_bags__gt=0).order_by('-total_bags')
    
    # Godown-wise inventory summary
    godown_summaries = active_inventory.values(
        'godown__name', 'godown__code'
    ).annotate(
        total_bags=Sum('good_bags_available'),
        total_products=Count('product', distinct=True),
        total_batches=Count('batch_id')
    ).filter(total_bags__gt=0).order_by('-total_bags')
    
    # Overall statistics
    summary_stats = active_inventory.aggregate(
        total_inventory_entries=Count('batch_id'),
        total_bags_available=Sum('good_bags_available'),
        total_bags_received=Sum('total_bags_received'),
        total_damaged_bags=Sum('damaged_bags'),
        total_reserved_bags=Sum('good_bags_reserved'),
        unique_products=Count('product', distinct=True),
        unique_godowns=Count('godown', distinct=True)
    )
    
    # Recent inventory additions (last 10)
    recent_additions = GodownInventory.objects.select_related(
        'product', 'godown', 'order_in_transit'
    ).order_by('-received_date')[:10]
    
    # Low stock alerts (products with less than 50 bags)
    low_stock_products = product_summaries.filter(total_bags__lt=50)
    
    context = {
        'product_summaries': product_summaries,
        'godown_summaries': godown_summaries,
        'summary_stats': summary_stats,
        'recent_additions': recent_additions,
        'low_stock_products': low_stock_products,
        'title': 'Godown Inventory Dashboard'
    }
    
    return render(request, 'godown/inventory/dashboard.html', context)


@login_required
def godown_inventory_list(request):
    """List all GodownInventory items with search and filtering"""

    # Get filter parameters
    godown_filter = request.GET.get('godown', '')
    product_filter = request.GET.get('product', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all records
    inventory_items = GodownInventory.objects.select_related(
        'product', 'godown', 'order_in_transit'
    ).order_by('-received_date')

    # Apply filters
    if godown_filter:
        inventory_items = inventory_items.filter(godown_id=godown_filter)
    
    if product_filter:
        inventory_items = inventory_items.filter(product_id=product_filter)
        
    if status_filter:
        inventory_items = inventory_items.filter(status=status_filter)
    
    if search_query:
        inventory_items = inventory_items.filter(
            Q(batch_id__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(godown__name__icontains=search_query) |
            Q(order_in_transit__eway_bill_number__icontains=search_query)
        )
    
    if date_from:
        inventory_items = inventory_items.filter(received_date__date__gte=date_from)
    
    if date_to:
        inventory_items = inventory_items.filter(received_date__date__lte=date_to)

    # Calculate summary statistics for the filtered results
    summary_stats = inventory_items.aggregate(
        total_records=Count('batch_id'),
        total_bags_available=Sum('good_bags_available'),
        total_bags_received=Sum('total_bags_received'),
        total_damaged_bags=Sum('damaged_bags'),
        total_reserved_bags=Sum('good_bags_reserved')
    )
    
    # Status counts for dashboard cards
    status_counts = inventory_items.values('status').annotate(
        count=Count('batch_id')
    ).order_by('status')

    # Unique product and godown
    product_choices = Product.objects.filter(is_active=True).order_by('name')
    godown_choices = GodownLocation.objects.filter(is_active=True).order_by('name')

    # Pagination
    paginator = Paginator(inventory_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'godown_filter': godown_filter,
        'product_filter': product_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'summary_stats': summary_stats,
        'status_counts': status_counts,
        'product_choices': product_choices,
        'godown_choices': godown_choices,
        'title': 'Godown Inventory List'
    }
    return render(request, 'godown/inventory/list.html', context)


@login_required
def godown_inventory_create(request):
    """Create a new GodownInventory item"""

    if request.method == 'POST':
        form = GodownInventoryForm(request.POST)
        if form.is_valid():
            inventory = form.save(commit=False)
            inventory.created_by = request.user
            inventory.save()
            messages.success(request, 'Godown inventory item created successfully.')
            return redirect('godown_inventory_list')
        else:
            messages.error(request, 'Error creating godown inventory item.')
    else:
        form = GodownInventoryForm()

    context = {
        'form': form,
        'title': 'Create Godown Inventory Item',
        'submit_text': 'Create Inventory'
    }
    return render(request, 'godown/inventory/form.html', context)


@login_required
def godown_inventory_detail(request, batch_id):
    """Display detailed view of a specific GodownInventory batch"""
    
    inventory = get_object_or_404(GodownInventory, batch_id=batch_id)
    
    # Calculate metrics
    total_bags_accounted = inventory.good_bags_available + inventory.good_bags_reserved + inventory.damaged_bags
    utilization_percentage = 0
    if inventory.total_bags_received > 0:
        utilization_percentage = (total_bags_accounted / inventory.total_bags_received) * 100
    
    availability_percentage = 0
    if inventory.good_bags_available > 0 and inventory.total_bags_received > 0:
        availability_percentage = (inventory.good_bags_available / inventory.total_bags_received) * 100
    
    # Get related batches from same transit order
    related_batches = GodownInventory.objects.filter(
        order_in_transit=inventory.order_in_transit
    ).exclude(batch_id=batch_id).select_related('product', 'godown')
    
    # Get other batches of same product in same godown
    similar_batches = GodownInventory.objects.filter(
        product=inventory.product,
        godown=inventory.godown,
        status='ACTIVE'
    ).exclude(batch_id=batch_id)[:5]
    
    context = {
        'inventory': inventory,
        'utilization_percentage': round(utilization_percentage, 1),
        'availability_percentage': round(availability_percentage, 1),
        'total_bags_accounted': total_bags_accounted,
        'related_batches': related_batches,
        'similar_batches': similar_batches,
        'title': f'Inventory Details - {inventory.batch_id}'
    }
    
    return render(request, 'godown/inventory/detail.html', context)


@login_required
def godown_inventory_update(request, batch_id):
    """Update an existing GodownInventory item"""
    
    inventory = get_object_or_404(GodownInventory, batch_id=batch_id)
    
    if request.method == 'POST':
        form = GodownInventoryForm(request.POST, instance=inventory)
        if form.is_valid():
            form.save()
            messages.success(request, 'Godown inventory item updated successfully.')
            return redirect('godown_inventory_detail', batch_id=batch_id)
        else:
            messages.error(request, 'Error updating godown inventory item.')
    else:
        form = GodownInventoryForm(instance=inventory)

    context = {
        'form': form,
        'inventory': inventory,
        'title': f'Update Inventory - {inventory.batch_id}',
        'submit_text': 'Update Inventory'
    }
    return render(request, 'godown/inventory/form.html', context)


# =============================================================================
# LOADING RECORD VIEWS - Simplified for minimally skilled users
# =============================================================================

@login_required
def loading_record_list(request):
    """List all Loading Records with simple search and filtering"""
    
    # Get filter parameters
    godown_filter = request.GET.get('godown', '')
    dealer_filter = request.GET.get('dealer', '')
    search_query = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all records
    loading_records = LoadingRequest.objects.select_related(
        'godown', 'dealer', 'product', 'supervised_by', 'created_by'
    ).order_by('-created_at')
    
    # Apply filters
    if godown_filter:
        loading_records = loading_records.filter(godown_id=godown_filter)
    
    if dealer_filter:
        loading_records = loading_records.filter(dealer_id=dealer_filter)
    
    if search_query:
        loading_records = loading_records.filter(
            Q(loading_request_id__icontains=search_query) |
            Q(dealer__name__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(godown__name__icontains=search_query)
        )
    
    if date_from:
        loading_records = loading_records.filter(created_at__date__gte=date_from)
    
    if date_to:
        loading_records = loading_records.filter(created_at__date__lte=date_to)
    
    # Calculate summary statistics
    summary_stats = loading_records.aggregate(
        total_records=Count('loading_request_id'),
        total_requested_bags=Sum('requested_bags'),
        total_loaded_bags=Sum('loaded_bags'),
    )
    
    # Completion percentage
    if summary_stats['total_requested_bags'] and summary_stats['total_loaded_bags']:
        completion_percentage = (summary_stats['total_loaded_bags'] / summary_stats['total_requested_bags']) * 100
    else:
        completion_percentage = 0
    summary_stats['completion_percentage'] = round(completion_percentage, 1)
    
    # Get choices for filter dropdowns
    godown_choices = GodownLocation.objects.filter(is_active=True).order_by('name')
    dealer_choices = Dealer.objects.filter(is_active=True).order_by('name')
    
    # Pagination
    paginator = Paginator(loading_records, 15)  # Show 15 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'godown_filter': godown_filter,
        'dealer_filter': dealer_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'summary_stats': summary_stats,
        'godown_choices': godown_choices,
        'dealer_choices': dealer_choices,
        'title': 'Loading Records'
    }
    
    return render(request, 'godown/loadingrecord/list.html', context)


@login_required
def loading_record_create(request):
    """Create a new Loading Record with step-by-step interface"""
    
    if request.method == 'POST':
        form = LoadingRecordForm(request.POST)
        if form.is_valid():
            loading_record = form.save(commit=False)
            loading_record.created_by = request.user
            loading_record.save()
            
            messages.success(
                request, 
                f'Loading Record "{loading_record.loading_request_id}" has been created successfully! '
                f'{loading_record.loaded_bags} bags loaded for {loading_record.dealer.name}.'
            )
            return redirect('loading_record_detail', loading_request_id=loading_record.loading_request_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoadingRecordForm()
    
    context = {
        'form': form,
        'title': 'New Loading Record',
        'submit_text': 'Save Loading Record',
        'help_text': 'Fill out this simple form to record a loading operation'
    }
    
    return render(request, 'godown/loadingrecord/form.html', context)


@login_required
def loading_record_detail(request, loading_request_id):
    """Display detailed view of a specific Loading Record"""
    
    loading_record = get_object_or_404(LoadingRequest, loading_request_id=loading_request_id)
    
    # Calculate completion metrics
    completion_percentage = 0
    if loading_record.requested_bags > 0:
        completion_percentage = (loading_record.loaded_bags / loading_record.requested_bags) * 100
    
    # Calculate difference
    bags_difference = loading_record.loaded_bags - loading_record.requested_bags
    
    # Get recent loading records for same dealer
    recent_records = LoadingRequest.objects.filter(
        dealer=loading_record.dealer
    ).exclude(loading_request_id=loading_record.loading_request_id).select_related(
        'product', 'godown'
    ).order_by('-created_at')[:5]
    
    context = {
        'loading_record': loading_record,
        'completion_percentage': round(completion_percentage, 1),
        'bags_difference': bags_difference,
        'recent_records': recent_records,
        'title': f'Loading Record - {loading_record.loading_request_id}'
    }
    
    return render(request, 'godown/loadingrecord/detail.html', context)


@login_required
def loading_record_update(request, loading_request_id):
    """Update an existing Loading Record"""
    
    loading_record = get_object_or_404(LoadingRequest, loading_request_id=loading_request_id)
    
    if request.method == 'POST':
        form = LoadingRecordForm(request.POST, instance=loading_record)
        if form.is_valid():
            updated_record = form.save(commit=False)
            updated_record.updated_at = timezone.now()
            updated_record.save()
            
            messages.success(
                request, 
                f'Loading Record "{updated_record.loading_request_id}" has been updated successfully!'
            )
            return redirect('loading_record_detail', loading_request_id=updated_record.loading_request_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoadingRecordForm(instance=loading_record)
    
    context = {
        'form': form,
        'loading_record': loading_record,
        'title': f'Update Loading Record - {loading_record.loading_request_id}',
        'submit_text': 'Update Record',
        'help_text': 'Make changes to this loading record'
    }
    
    return render(request, 'godown/loadingrecord/form.html', context)


@login_required
def loading_record_dashboard(request):
    """Simple dashboard showing key loading metrics"""
    
    # Today's records
    today = timezone.now().date()
    today_records = LoadingRequest.objects.filter(created_at__date=today)
    
    # This week's records
    week_ago = today - timezone.timedelta(days=7)
    week_records = LoadingRequest.objects.filter(created_at__date__gte=week_ago)
    
    # Key metrics
    total_records = LoadingRequest.objects.count()
    today_count = today_records.count()
    week_count = week_records.count()
    
    # Bag metrics
    today_stats = today_records.aggregate(
        requested=Sum('requested_bags'),
        loaded=Sum('loaded_bags')
    )
    
    week_stats = week_records.aggregate(
        requested=Sum('requested_bags'),
        loaded=Sum('loaded_bags')
    )
    
    # Recent records (last 10)
    recent_records = LoadingRequest.objects.select_related(
        'dealer', 'product', 'godown', 'supervised_by'
    ).order_by('-created_at')[:10]
    
    # Top dealers by loading volume
    top_dealers = LoadingRequest.objects.values(
        'dealer__name', 'dealer__code'
    ).annotate(
        total_loads=Count('loading_request_id'),
        total_bags=Sum('loaded_bags')
    ).order_by('-total_bags')[:5]
    
    context = {
        'total_records': total_records,
        'today_count': today_count,
        'week_count': week_count,
        'today_stats': today_stats,
        'week_stats': week_stats,
        'recent_records': recent_records,
        'top_dealers': top_dealers,
        'title': 'Loading Records Dashboard'
    }
    
    return render(request, 'godown/loadingrecord/dashboard.html', context)
