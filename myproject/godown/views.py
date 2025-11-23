from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Max
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import timedelta
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .models import OrderInTransit, GodownLocation, CrossoverRecord, GodownInventory, LoadingRequest, GodownDailyBalance, LoadingRequestImage
from .forms import OrderInTransitForm, CrossoverRecordForm, GodownInventoryForm, LoadingRecordForm
from sylvia.models import Product, Dealer
from sylvia.storage import KrutrimStorageClient


@login_required
def godown_home(request):
    """Render the godown home page with navigation links and simple details"""
    from django.db.models import Max
    
    today = timezone.now().date()
    
    # Get godown summaries - simplified approach
    from .models import GodownDailyBalance
    
    # Get latest daily balances for all godown-product combinations
    latest_dates = GodownDailyBalance.objects.filter(
        balance_date__lte=today
    ).values(
        'godown', 'product'
    ).annotate(
        latest_date=Max('balance_date')
    )
    
    # Get the actual balance records for those latest dates
    latest_balances = []
    for date_info in latest_dates:
        balance = GodownDailyBalance.objects.filter(
            godown_id=date_info['godown'],
            product_id=date_info['product'],
            balance_date=date_info['latest_date']
        ).select_related('godown', 'product').first()
        
        if balance:
            latest_balances.append(balance)
    
    # Group by godown for summary
    godown_summaries = []
    godown_data = {}
    
    for balance in latest_balances:
        godown_key = f"{balance.godown.code}_{balance.godown.name}"
        
        if godown_key not in godown_data:
            godown_data[godown_key] = {
                'godown_id': balance.godown.id,
                'godown_name': balance.godown.name,
                'godown_code': balance.godown.code,
                'total_bags': 0,
                'good_condition_bags': 0,
                'damaged_bags': 0,
                'products_count': 0,
            }
        
        if balance.closing_balance > 0:
            godown_data[godown_key]['total_bags'] += balance.closing_balance
            godown_data[godown_key]['good_condition_bags'] += balance.good_condition_bags
            godown_data[godown_key]['damaged_bags'] += balance.damaged_bags
            godown_data[godown_key]['products_count'] += 1
    
    # Convert to sorted list
    godown_summaries = sorted(
        [data for data in godown_data.values() if data['total_bags'] > 0],
        key=lambda x: x['total_bags'], 
        reverse=True
    )
    
    # Today's loading statistics
    today_loadings = LoadingRequest.objects.filter(created_at__date=today)
    today_loading_count = today_loadings.count()
    today_bags_requested = today_loadings.aggregate(total=Sum('requested_bags'))['total'] or 0
    today_bags_loaded = today_loadings.aggregate(total=Sum('loaded_bags'))['total'] or 0
    
    context = {
        'godown_summaries': godown_summaries,
        'today_loading_count': today_loading_count,
        'today_bags_requested': today_bags_requested,
        'today_bags_loaded': today_bags_loaded,
        'today_date': today,
    }
    
    return render(request, 'godown/home.html', context) 


@login_required
def godown_detail(request, godown_id):
    """Display detailed view for a specific godown using GodownDailyBalance data"""
    from django.db.models import Max
    
    # Get the godown
    godown = get_object_or_404(GodownLocation, id=godown_id)
    today = timezone.now().date()
    
    # Get latest daily balances for this godown - one per product
    latest_dates = GodownDailyBalance.objects.filter(
        godown=godown,
        balance_date__lte=today
    ).values(
        'product'
    ).annotate(
        latest_date=Max('balance_date')
    )
    
    # Get the actual balance records for those latest dates
    latest_balances = []
    for date_info in latest_dates:
        balance = GodownDailyBalance.objects.filter(
            godown=godown,
            product_id=date_info['product'],
            balance_date=date_info['latest_date']
        ).select_related('product').first()
        
        if balance and balance.closing_balance > 0:
            latest_balances.append(balance)
    
    # Calculate summary metrics
    total_bags = sum(balance.closing_balance for balance in latest_balances)
    total_good_bags = sum(balance.good_condition_bags for balance in latest_balances)
    total_damaged_bags = sum(balance.damaged_bags for balance in latest_balances)
    products_count = len(latest_balances)
    
    # Calculate utilization percentage (assuming some capacity metrics)
    utilization_percentage = 0
    if godown.total_capacity:
        # Simple utilization based on total bags (assuming 50kg per bag, 1 MT per cubic meter)
        estimated_volume_used = total_bags * 0.05  # 50kg bags = 0.05 MT
        utilization_percentage = (estimated_volume_used / float(godown.total_capacity)) * 100
    
    # Get recent activity - last 10 balance changes for this godown
    recent_activity = GodownDailyBalance.objects.filter(
        godown=godown,
        balance_date__lte=today
    ).select_related('product').order_by('-balance_date')[:10]
    
    # Get product-wise breakdown
    product_breakdown = [{
        'product_name': balance.product.name,
        'product_code': balance.product.code,
        'closing_balance': balance.closing_balance,
        'good_condition_bags': balance.good_condition_bags,
        'damaged_bags': balance.damaged_bags,
        'last_updated': balance.balance_date,
        'balance_status': balance.get_balance_status_display(),
    } for balance in latest_balances]
    
    context = {
        'godown': godown,
        'total_bags': total_bags,
        'total_good_bags': total_good_bags,
        'total_damaged_bags': total_damaged_bags,
        'products_count': products_count,
        'utilization_percentage': round(utilization_percentage, 1) if utilization_percentage else 0,
        'product_breakdown': product_breakdown,
        'recent_activity': recent_activity,
        'today_date': today,
    }
    
    return render(request, 'godown/godown_detail.html', context)


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
    """Create a new Loading Record with inventory validation and image upload"""

    if request.method == 'POST':
        form = LoadingRecordForm(request.POST, request.FILES)
        if form.is_valid():
            loading_record = form.save(commit=False)
            loading_record.created_by = request.user

            # Validate inventory availability before saving
            from .utils import LedgerCalculator
            current_balance = LedgerCalculator.calculate_current_balance(
                loading_record.godown,
                loading_record.product
            )

            if loading_record.loaded_bags > current_balance:
                messages.error(
                    request,
                    f'Insufficient inventory! Available: {current_balance} bags, '
                    f'Requested: {loading_record.loaded_bags} bags. '
                    f'Please check current inventory levels.'
                )
                context = {
                    'form': form,
                    'title': 'New Loading Record',
                    'submit_text': 'Save Loading Record',
                    'help_text': 'Fill out this simple form to record a loading operation',
                    'current_balance': current_balance,
                    'inventory_warning': True
                }
                return render(request, 'godown/loadingrecord/form.html', context)

            loading_record.save()

            # Handle image uploads
            uploaded_images = request.FILES.getlist('loading_images')
            uploaded_count = 0
            failed_uploads = []

            if uploaded_images:
                storage = KrutrimStorageClient()

                for idx, image_file in enumerate(uploaded_images):
                    # Upload to Krutrim storage
                    success, url_or_error, storage_key, metadata = storage.upload_loading_image(
                        image_file, loading_record.loading_request_id
                    )

                    if success:
                        # Create LoadingRequestImage record
                        LoadingRequestImage.objects.create(
                            loading_request=loading_record,
                            image_url=url_or_error,
                            storage_key=storage_key,
                            original_filename=metadata['original_filename'],
                            file_size=metadata['file_size'],
                            content_type=metadata['content_type'],
                            is_primary=(idx == 0),  # First image is primary
                            created_by=request.user
                        )
                        uploaded_count += 1
                    else:
                        failed_uploads.append(f"{image_file.name}: {url_or_error}")

            # Success message
            success_msg = f'Loading Record "{loading_record.loading_request_id}" has been created successfully! ' \
                         f'{loading_record.loaded_bags} bags loaded for {loading_record.dealer.name}. ' \
                         f'Remaining inventory: {current_balance - loading_record.loaded_bags} bags.'

            if uploaded_count > 0:
                success_msg += f' {uploaded_count} image(s) uploaded.'

            messages.success(request, success_msg)

            if failed_uploads:
                messages.warning(
                    request,
                    f'Failed to upload {len(failed_uploads)} image(s): ' + '; '.join(failed_uploads)
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
    """Display detailed view of a Loading Record with ledger integration and images"""

    loading_record = get_object_or_404(LoadingRequest, loading_request_id=loading_request_id)

    # Calculate completion metrics
    completion_percentage = 0
    if loading_record.requested_bags > 0:
        completion_percentage = (loading_record.loaded_bags / loading_record.requested_bags) * 100

    # Calculate difference
    bags_difference = loading_record.loaded_bags - loading_record.requested_bags

    # Get ledger entry for this loading record
    from .models import GodownInventoryLedger
    ledger_entry = GodownInventoryLedger.objects.filter(
        source_loading_request=loading_record,
        transaction_type='OUTWARD_LOADING'
    ).first()

    # Get current inventory balance for this product at this godown
    from .utils import LedgerCalculator
    current_balance = LedgerCalculator.calculate_current_balance(
        loading_record.godown,
        loading_record.product
    )

    # Get recent loading records for same dealer
    recent_records = LoadingRequest.objects.filter(
        dealer=loading_record.dealer
    ).exclude(loading_request_id=loading_record.loading_request_id).select_related(
        'product', 'godown'
    ).order_by('-created_at')[:5]

    # Get loading transactions summary for this product-godown combination (last 7 days)
    from datetime import timedelta
    week_ago = timezone.now().date() - timedelta(days=7)
    loading_summary = LedgerCalculator.get_loading_transactions_summary(
        godown=loading_record.godown,
        product=loading_record.product,
        start_date=week_ago,
        end_date=timezone.now().date()
    )

    # Get uploaded images for this loading request
    loading_images = loading_record.loading_images.all().order_by('-is_primary', '-upload_timestamp')

    context = {
        'loading_record': loading_record,
        'completion_percentage': round(completion_percentage, 1),
        'bags_difference': bags_difference,
        'recent_records': recent_records,
        'ledger_entry': ledger_entry,
        'current_balance': current_balance,
        'loading_summary': loading_summary,
        'loading_images': loading_images,
        'title': f'Loading Record - {loading_record.loading_request_id}'
    }

    return render(request, 'godown/loadingrecord/detail.html', context)


@login_required
def loading_record_update(request, loading_request_id):
    """Update an existing Loading Record with inventory validation and image upload"""

    loading_record = get_object_or_404(LoadingRequest, loading_request_id=loading_request_id)

    if request.method == 'POST':
        form = LoadingRecordForm(request.POST, request.FILES, instance=loading_record)
        if form.is_valid():
            updated_record = form.save(commit=False)

            # Validate inventory availability for changes
            if updated_record.loaded_bags != loading_record.loaded_bags:
                from .utils import LedgerCalculator
                current_balance = LedgerCalculator.calculate_current_balance(
                    updated_record.godown,
                    updated_record.product
                )

                # Calculate the additional bags needed (if increase) or returned (if decrease)
                bag_change = updated_record.loaded_bags - loading_record.loaded_bags

                if bag_change > 0 and bag_change > current_balance:
                    messages.error(
                        request,
                        f'Insufficient inventory for increase! Additional bags needed: {bag_change}, '
                        f'Available: {current_balance} bags. '
                        f'Please check current inventory levels.'
                    )
                    context = {
                        'form': form,
                        'loading_record': loading_record,
                        'title': f'Update Loading Record - {loading_record.loading_request_id}',
                        'submit_text': 'Update Record',
                        'help_text': 'Make changes to this loading record',
                        'current_balance': current_balance,
                        'inventory_warning': True
                    }
                    return render(request, 'godown/loadingrecord/form.html', context)

            updated_record.updated_at = timezone.now()
            updated_record.save()

            # Handle new image uploads
            uploaded_images = request.FILES.getlist('loading_images')
            uploaded_count = 0
            failed_uploads = []

            if uploaded_images:
                storage = KrutrimStorageClient()

                # Check if this is the first image (make it primary if no images exist)
                existing_images_count = loading_record.loading_images.count()

                for idx, image_file in enumerate(uploaded_images):
                    # Upload to Krutrim storage
                    success, url_or_error, storage_key, metadata = storage.upload_loading_image(
                        image_file, loading_record.loading_request_id
                    )

                    if success:
                        # Create LoadingRequestImage record
                        LoadingRequestImage.objects.create(
                            loading_request=loading_record,
                            image_url=url_or_error,
                            storage_key=storage_key,
                            original_filename=metadata['original_filename'],
                            file_size=metadata['file_size'],
                            content_type=metadata['content_type'],
                            is_primary=(existing_images_count == 0 and idx == 0),  # First image is primary if no previous images
                            created_by=request.user
                        )
                        uploaded_count += 1
                    else:
                        failed_uploads.append(f"{image_file.name}: {url_or_error}")

            # Success message
            success_msg = f'Loading Record "{updated_record.loading_request_id}" has been updated successfully!'

            if uploaded_count > 0:
                success_msg += f' {uploaded_count} image(s) uploaded.'

            messages.success(request, success_msg)

            if failed_uploads:
                messages.warning(
                    request,
                    f'Failed to upload {len(failed_uploads)} image(s): ' + '; '.join(failed_uploads)
                )

            return redirect('loading_record_detail', loading_request_id=updated_record.loading_request_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoadingRecordForm(instance=loading_record)

    # Get existing images for display
    existing_images = loading_record.loading_images.all().order_by('-is_primary', '-upload_timestamp')

    context = {
        'form': form,
        'loading_record': loading_record,
        'existing_images': existing_images,
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


@login_required
@csrf_exempt
def check_inventory_availability(request):
    """AJAX endpoint to check available inventory for loading operations"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            godown_id = data.get('godown_id')
            product_id = data.get('product_id')
            requested_bags = int(data.get('requested_bags', 0))
            
            if not godown_id or not product_id:
                return JsonResponse({'success': False, 'error': 'Godown and product are required'})
            
            from .models import GodownLocation
            from sylvia.models import Product
            from .utils import LedgerCalculator
            
            godown = GodownLocation.objects.get(pk=godown_id)
            product = Product.objects.get(pk=product_id)
            
            # Get current balance
            current_balance = LedgerCalculator.calculate_current_balance(godown, product)
            
            # Check availability
            is_available = requested_bags <= current_balance
            remaining_after_load = current_balance - requested_bags if is_available else current_balance
            
            # Get recent loading activity for context
            from datetime import timedelta
            week_ago = timezone.now().date() - timedelta(days=7)
            loading_summary = LedgerCalculator.get_loading_transactions_summary(
                godown=godown,
                product=product,
                start_date=week_ago,
                end_date=timezone.now().date()
            )
            
            return JsonResponse({
                'success': True,
                'current_balance': current_balance,
                'requested_bags': requested_bags,
                'is_available': is_available,
                'remaining_after_load': remaining_after_load,
                'shortage': max(0, requested_bags - current_balance),
                'weekly_loaded': loading_summary['loading_stats'].get('total_loaded_bags', 0),
                'godown_name': godown.name,
                'product_name': product.name
            })
            
        except (ValueError, json.JSONDecodeError, GodownLocation.DoesNotExist, Product.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# =============================================================================
# GODOWN AUDIT CHECKLIST PDF GENERATION
# =============================================================================

@login_required
def generate_audit_pdf(request, godown_id):
    """Generate comprehensive godown audit checklist PDF"""

    godown = get_object_or_404(GodownLocation, id=godown_id)
    today = timezone.now().date()

    # Fetch inventory data
    latest_dates = GodownDailyBalance.objects.filter(
        godown=godown,
        balance_date__lte=today
    ).values('product').annotate(latest_date=Max('balance_date'))

    inventory_data = []
    for date_info in latest_dates:
        balance = GodownDailyBalance.objects.filter(
            godown=godown,
            product_id=date_info['product'],
            balance_date=date_info['latest_date']
        ).select_related('product').first()

        if balance and balance.closing_balance > 0:
            inventory_data.append({
                'product_name': balance.product.name,
                'product_code': balance.product.code,
                'closing_balance': balance.closing_balance,
                'good_bags': balance.good_condition_bags,
                'damaged_bags': balance.damaged_bags,
                'balance_date': balance.balance_date,
            })

    # Fetch loading records from last 30 days
    thirty_days_ago = today - timedelta(days=30)
    loading_records = LoadingRequest.objects.filter(
        godown=godown,
        created_at__date__gte=thirty_days_ago
    ).select_related('dealer', 'product').order_by('-created_at')[:10]

    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=20*mm, leftMargin=20*mm,
                           topMargin=20*mm, bottomMargin=20*mm)

    # Container for PDF elements
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2c3e50'),
    )

    checkbox_style = ParagraphStyle(
        'Checkbox',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceAfter=4,
    )

    # Title
    elements.append(Paragraph(f"<b>Shyam Distributors | AUDIT CHECKLIST</b>", title_style))
    elements.append(Paragraph(f"<b>{godown.name} ({godown.code})</b>", title_style))
    elements.append(Paragraph(f"Audit Date: {today.strftime('%B %d, %Y')}", normal_style))
    elements.append(Spacer(1, 10*mm))

    # Section 1: Structural Audit
    elements.append(Paragraph("<b>1. STRUCTURAL AUDIT CHECKLIST</b>", heading_style))
    elements.append(Paragraph("<b>Auditor:</b> _________________ | <b>Date:</b> _________", normal_style))
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("<b>VISUAL INSPECTION (DO-CONFIRM)</b>", normal_style))
    elements.append(Spacer(1, 2*mm))

    structural_checks = [
        "[ ] <b>Roof:</b> No visible leaks, cracks, or water stains",
        "[ ] <b>Walls:</b> No major cracks, dampness, or structural damage",
        "[ ] <b>Floor:</b> Surface intact, no major cracks or uneven settling",
        "[ ] <b>Windows/Ventilation:</b> All functional, no broken panes, adequate airflow",
        "[ ] <b>Doors:</b> Open/close properly, no warping or damage",
        "[ ] <b>Lighting:</b> All lights functional, adequate visibility",
    ]

    for check in structural_checks:
        elements.append(Paragraph(check, checkbox_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>CEMENT STORAGE CONDITIONS</b>", normal_style))
    elements.append(Spacer(1, 2*mm))

    storage_checks = [
        "[ ] <b>Elevation:</b> Cement bags stored with tarpaulins on the ground",
        "[ ] <b>Wall clearance:</b> Minimum 12 inches from walls",
        "[ ] <b>Stack height:</b> Not exceeding safe limits (max 12 bags high)",
        "[ ] <b>Coverage:</b> Protected from direct weather exposure",
    ]

    for check in storage_checks:
        elements.append(Paragraph(check, checkbox_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>OVERALL STRUCTURAL RATING</b>", normal_style))
    elements.append(Paragraph("Rate overall condition (circle one): <b>1</b> (Critical) | <b>2</b> (Major concerns) | <b>3</b> (Moderate) | <b>4</b> (Minor) | <b>5</b> (Excellent)", normal_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("<b>Action required if rated 1-2:</b> _________________________________", normal_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("<b>Auditor Signature:</b> _________________ <b>Time:</b> _________", normal_style))

    elements.append(PageBreak())

    # Section 2: Security Audit
    elements.append(Paragraph("<b>2. SECURITY AUDIT CHECKLIST</b>", heading_style))
    elements.append(Paragraph("<b>Auditor:</b> _________________ | <b>Date:</b> _________", normal_style))
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("<b>PHYSICAL SECURITY (DO-CONFIRM)</b>", normal_style))
    elements.append(Spacer(1, 2*mm))

    security_checks = [
        "[ ] <b>Main Lock:</b> Functions smoothly, no signs of tampering",
        "[ ] <b>Spare Keys:</b> Accounted for (Expected: ___ | Present: ___)",
        "[ ] <b>Door Hinges:</b> Secure, no loose bolts",
    ]

    for check in security_checks:
        elements.append(Paragraph(check, checkbox_style))

    elements.append(Spacer(1, 8*mm))

    # Section 3: Inventory Audit with DATABASE DATA
    elements.append(Paragraph("<b>3. INVENTORY AUDIT CHECKLIST</b>", heading_style))
    elements.append(Paragraph("<b>Duration:</b> 30-45 minutes", normal_style))
    elements.append(Paragraph("<b>Auditor:</b> _________________ | <b>Date:</b> _________", normal_style))
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("<b>PRE-AUDIT PREPARATION</b>", normal_style))
    elements.append(Paragraph("[ ] <b>Software Opening Balance Retrieved:</b> Date/Time: _________", checkbox_style))
    elements.append(Paragraph("[ ] <b>Previous Audit Report:</b> Reviewed for pending issues", checkbox_style))
    elements.append(Spacer(1, 5*mm))

    # Opening Balance from Software (Database)
    elements.append(Paragraph("<b>OPENING BALANCE FROM SOFTWARE:</b>", normal_style))
    elements.append(Spacer(1, 3*mm))

    if inventory_data:
        # Create table with inventory data (without Item column, no colors)
        inventory_table_data = [
            ['Brand/Grade', 'Bags Count', 'Good Bags', 'Damaged', 'Last Updated']
        ]

        for item in inventory_data:
            inventory_table_data.append([
                f"{item['product_name']}\n({item['product_code']})",
                str(item['closing_balance']),
                str(item['good_bags']),
                str(item['damaged_bags']),
                item['balance_date'].strftime('%Y-%m-%d')
            ])

        inventory_table = Table(inventory_table_data, colWidths=[95, 70, 70, 65, 75])
        inventory_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(inventory_table)
    else:
        elements.append(Paragraph("<i>No inventory data available for this godown.</i>", normal_style))

    elements.append(Spacer(1, 8*mm))

    # Physical Count (Empty for manual entry, without Item column)
    elements.append(Paragraph("<b>PHYSICAL COUNT:</b>", normal_style))
    elements.append(Spacer(1, 3*mm))

    physical_count_table_data = [
        ['Brand/Grade', 'Bags Count', 'Loose Bags', 'Damaged'],
        ['___________', '_______', '_______', '_____'],
        ['___________', '_______', '_______', '_____'],
        ['___________', '_______', '_______', '_____'],
    ]

    physical_count_table = Table(physical_count_table_data, colWidths=[105, 90, 90, 90])
    physical_count_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(physical_count_table)

    elements.append(Spacer(1, 8*mm))

    # Verification Checks
    elements.append(Paragraph("<b>VERIFICATION CHECKS</b>", normal_style))
    elements.append(Spacer(1, 2*mm))

    verification_checks = [
        "[ ] <b>Variance Analysis:</b> Difference = Physical - Software",
        "  • Acceptable range: ±___ bags",
        "  • Variance: _____ bags (Within/Outside acceptable range)",
        "[ ] <b>FIFO Compliance:</b> Older stock accessible and being used first",
        "[ ] <b>Damaged Stock:</b> Segregated and marked clearly",
        "[ ] <b>Manufacturing Dates:</b> Checked on random samples (min. 10%)",
        "  • Oldest cement date found: __________",
        "  • Action if >90 days: __________________",
        "[ ] <b>Brand/Grade Segregation:</b> Properly separated and labeled",
    ]

    for check in verification_checks:
        elements.append(Paragraph(check, checkbox_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>DISCREPANCY RESOLUTION</b>", normal_style))
    elements.append(Paragraph("[ ] Recounted suspected areas", checkbox_style))
    elements.append(Paragraph("[ ] Checked recent loading records", checkbox_style))
    elements.append(Paragraph("[ ] Verified any damaged/lost material documentation", checkbox_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("<b>Variance Reason (if identified):</b> _________________________", normal_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("<b>Approved by Manager (if variance >___ bags):</b> ______________", normal_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("<b>Auditor Signature:</b> _________________ <b>Time:</b> _________", normal_style))

    elements.append(PageBreak())

    # Section 4: Records & Administration Audit with LOADING DATA
    elements.append(Paragraph("<b>4. RECORDS & ADMINISTRATION AUDIT CHECKLIST</b>", heading_style))
    elements.append(Paragraph("<b>Frequency:</b> Monthly | <b>Duration:</b> 20-30 minutes", normal_style))
    elements.append(Paragraph("<b>Auditor:</b> _________________ | <b>Date:</b> _________", normal_style))
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("<b>RECENT LOADING RECORDS (Last 30 Days):</b>", normal_style))
    elements.append(Spacer(1, 3*mm))

    if loading_records.exists():
        loading_table_data = [
            ['Date', 'Loading ID', 'Dealer', 'Product', 'Bags Loaded']
        ]

        for record in loading_records[:10]:  # Limit to 10 records
            loading_table_data.append([
                record.created_at.strftime('%Y-%m-%d'),
                record.loading_request_id,
                record.dealer.name[:20],  # Truncate long names
                record.product.code,
                str(record.loaded_bags),
            ])

        loading_table = Table(loading_table_data, colWidths=[55, 75, 100, 60, 60])
        loading_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(loading_table)
    else:
        elements.append(Paragraph("<i>No loading records found in the last 30 days.</i>", normal_style))

    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("<b>DOCUMENT VERIFICATION</b>", normal_style))
    elements.append(Spacer(1, 2*mm))

    doc_checks = [
        "[ ] <b>Material Receiving Documents (MRD):</b> Last 30 days reviewed",
        "  • Total MRDs in period: _____",
        "  • Sample checked: _____ (minimum 10 or 20%, whichever is greater)",
        "[ ] <b>MRD-to-Software Matching:</b> All sampled MRDs entered in software",
        "  • Discrepancies found: _____ (Details below if any)",
        "[ ] <b>Loading Records:</b> Match software dispatch entries",
        "  • Sample checked: _____ loads",
        "  • Discrepancies: _____ (Details below if any)",
    ]

    for check in doc_checks:
        elements.append(Paragraph(check, checkbox_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>REGISTER MAINTENANCE</b>", normal_style))
    elements.append(Paragraph("[ ] Cash Disbursement to the labours", checkbox_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>COMPLIANCE CHECKS</b>", normal_style))
    elements.append(Paragraph("[ ] <b>Damaged Material Register:</b> All damaged stock documented", checkbox_style))

    elements.append(Spacer(1, 10*mm))

    # Audit Completion Summary
    elements.append(Paragraph("<b>AUDIT COMPLETION SUMMARY</b>", heading_style))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("<b>Overall Godown Status:</b> [] Satisfactory | [] Needs Attention | [] Critical", normal_style))
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("<b>Priority Actions Required:</b>", normal_style))
    elements.append(Paragraph("1. ___________________________________________", checkbox_style))
    elements.append(Paragraph("2. ___________________________________________", checkbox_style))
    elements.append(Paragraph("3. ___________________________________________", checkbox_style))

    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph("<b>Next Audit Due:</b> __________", normal_style))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("<b>Final Review & Signature:</b> _________________ <b>Date:</b> _________", normal_style))

    # Build PDF
    doc.build(elements)

    # Get PDF from buffer and return as response
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Godown_Audit_{godown.code}_{today.strftime("%Y%m%d")}.pdf"'
    response.write(pdf)

    return response


@login_required
def share_opening_stock_image(request):
    """Generate and serve a matrix image showing current stock for all products across all godowns"""
    from .utils import generate_opening_stock_matrix_image_bytes
    from django.db.models import Max

    today = timezone.now().date()

    # Get latest daily balances for all godown-product combinations (current stock)
    latest_dates = GodownDailyBalance.objects.filter(
        balance_date__lte=today
    ).values(
        'godown', 'product'
    ).annotate(
        latest_date=Max('balance_date')
    )

    # Build matrix data structure
    # products_matrix: {product_name: {godown_code: opening_stock}}
    products_matrix = {}
    godown_codes = []  # Ordered list of godown codes
    godown_names = {}  # Map code to name

    for date_info in latest_dates:
        balance = GodownDailyBalance.objects.filter(
            godown_id=date_info['godown'],
            product_id=date_info['product'],
            balance_date=date_info['latest_date']
        ).select_related('godown', 'product').first()

        if balance and balance.closing_balance > 0:
            product_name = balance.product.name
            godown_code = balance.godown.code
            godown_name = balance.godown.name

            # Initialize product entry if not exists
            if product_name not in products_matrix:
                products_matrix[product_name] = {}

            # Add stock for this godown (using closing_balance as current stock)
            products_matrix[product_name][godown_code] = balance.closing_balance/20  # Assuming 20 bags per ton

            # Track godown codes (maintain order)
            if godown_code not in godown_codes:
                godown_codes.append(godown_code)
                godown_names[godown_code] = godown_name

    # Format date string (e.g., "11 Nov, 2025")
    date_str = today.strftime("%d %b, %Y")

    # Generate matrix image
    img_io = generate_opening_stock_matrix_image_bytes(
        products_matrix=products_matrix,
        godown_codes=godown_codes,
        godown_names=godown_names,
        date_str=date_str
    )

    # Return as PNG response
    response = HttpResponse(img_io, content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="Current_Stock_Matrix_{today.strftime("%Y%m%d")}.png"'

    return response


@login_required
def stock_aging_report(request):
    """View to display stock aging report"""
    
    # Get all active inventory (including reserved and damaged)
    from django.db.models import F, Sum
    from .models import LoadingRequest
    
    active_inventory = GodownInventory.objects.annotate(
        total_physical=F('good_bags_available') + F('good_bags_reserved') + F('damaged_bags')
    ).filter(
        total_physical__gt=0
    ).select_related('product').order_by('received_date')
    
    # Get total loaded quantity per product (FIFO deduction)
    # Filter by loaded_bags > 0 since status field is not used
    loading_data = LoadingRequest.objects.filter(
        loaded_bags__gt=0
    ).values('product').annotate(
        total_loaded=Sum('loaded_bags')
    )
    
    loading_map = {item['product']: item['total_loaded'] for item in loading_data}
    
    today = timezone.now().date()
    
    # Aggregate data by product
    product_data = {}
    
    for item in active_inventory:
        product_id = item.product.id
        product_name = item.product.name
        
        if product_id not in product_data:
            product_data[product_id] = {
                'product_name': product_name,
                'bucket_0_30': 0,
                'bucket_31_60': 0,
                'bucket_61_90': 0,
                'bucket_90_plus': 0,
                'total_stock': 0
            }
            
        # FIFO Deduction Logic
        current_qty = item.total_physical
        loaded_qty = loading_map.get(product_id, 0)
        
        if loaded_qty > 0:
            if loaded_qty >= current_qty:
                # Batch fully consumed
                loading_map[product_id] = loaded_qty - current_qty
                current_qty = 0
            else:
                # Batch partially consumed
                current_qty -= loaded_qty
                loading_map[product_id] = 0
        
        if current_qty > 0:
            # Calculate age
            age_days = (today - item.received_date.date()).days
            quantity_tons = current_qty / 20.0
            
            # Add to appropriate bucket
            if age_days <= 30:
                product_data[product_id]['bucket_0_30'] += quantity_tons
            elif age_days <= 60:
                product_data[product_id]['bucket_31_60'] += quantity_tons
            elif age_days <= 90:
                product_data[product_id]['bucket_61_90'] += quantity_tons
            else:
                product_data[product_id]['bucket_90_plus'] += quantity_tons
                
            product_data[product_id]['total_stock'] += quantity_tons

        # Determine Action (moved inside loop but logic remains per product)
        if product_data[product_id]['bucket_90_plus'] > 0:
            product_data[product_id]['action'] = "CRITICAL: Stop Sending"
            product_data[product_id]['action_class'] = "text-danger font-weight-bold"
        elif product_data[product_id]['bucket_61_90'] > 0:
            product_data[product_id]['action'] = "High Alert: Reduce Orders"
            product_data[product_id]['action_class'] = "text-warning font-weight-bold"
        elif product_data[product_id]['bucket_31_60'] > 0:
            product_data[product_id]['action'] = "Monitor Stock"
            product_data[product_id]['action_class'] = "text-info"
        else:
            product_data[product_id]['action'] = "Normal Procurement"
            product_data[product_id]['action_class'] = "text-success"
    
    # Convert to list and sort by total stock
    aging_data = sorted(
        product_data.values(),
        key=lambda x: x['total_stock'],
        reverse=True
    )
    
    # Calculate totals
    total_0_30 = sum(item['bucket_0_30'] for item in aging_data)
    total_31_60 = sum(item['bucket_31_60'] for item in aging_data)
    total_61_90 = sum(item['bucket_61_90'] for item in aging_data)
    total_90_plus = sum(item['bucket_90_plus'] for item in aging_data)
    grand_total = sum(item['total_stock'] for item in aging_data)
    
    context = {
        'aging_data': aging_data,
        'total_0_30': total_0_30,
        'total_31_60': total_31_60,
        'total_61_90': total_61_90,
        'total_90_plus': total_90_plus,
        'grand_total': grand_total,
        'title': 'Stock Aging Report'
    }
    
    return render(request, 'godown/reports/stock_aging.html', context)


@login_required
def stock_aging_image(request):
    """View to generate and return stock aging report image"""
    
    # Get all active inventory (including reserved and damaged)
    from django.db.models import F, Sum
    from .models import LoadingRequest
    
    active_inventory = GodownInventory.objects.annotate(
        total_physical=F('good_bags_available') + F('good_bags_reserved') + F('damaged_bags')
    ).filter(
        total_physical__gt=0
    ).select_related('product').order_by('received_date')
    
    # Get total loaded quantity per product (FIFO deduction)
    # Filter by loaded_bags > 0 since status field is not used
    loading_data = LoadingRequest.objects.filter(
        loaded_bags__gt=0
    ).values('product').annotate(
        total_loaded=Sum('loaded_bags')
    )
    
    loading_map = {item['product']: item['total_loaded'] for item in loading_data}
    
    today = timezone.now().date()
    
    # Aggregate data by product
    product_data = {}
    
    for item in active_inventory:
        product_id = item.product.id
        product_name = item.product.name
        
        if product_id not in product_data:
            product_data[product_id] = {
                'product_name': product_name,
                'bucket_0_30': 0,
                'bucket_31_60': 0,
                'bucket_61_90': 0,
                'bucket_90_plus': 0,
                'total_stock': 0
            }
            
        # FIFO Deduction Logic
        current_qty = item.total_physical
        loaded_qty = loading_map.get(product_id, 0)
        
        if loaded_qty > 0:
            if loaded_qty >= current_qty:
                # Batch fully consumed
                loading_map[product_id] = loaded_qty - current_qty
                current_qty = 0
            else:
                # Batch partially consumed
                current_qty -= loaded_qty
                loading_map[product_id] = 0
        
        if current_qty > 0:
            # Calculate age
            age_days = (today - item.received_date.date()).days
            quantity_tons = current_qty / 20.0
            
            # Add to appropriate bucket
            if age_days <= 30:
                product_data[product_id]['bucket_0_30'] += quantity_tons
            elif age_days <= 60:
                product_data[product_id]['bucket_31_60'] += quantity_tons
            elif age_days <= 90:
                product_data[product_id]['bucket_61_90'] += quantity_tons
            else:
                product_data[product_id]['bucket_90_plus'] += quantity_tons
                
            product_data[product_id]['total_stock'] += quantity_tons
    
    # Convert to list and determine actions
    aging_data = []
    for p_id, data in product_data.items():
        # Determine action
        if data['bucket_90_plus'] > 0:
            data['action'] = "CRITICAL: Stop Sending"
            data['action_class'] = "text-danger"
        elif data['bucket_61_90'] > 0:
            data['action'] = "High Alert: Reduce Orders"
            data['action_class'] = "text-warning"
        elif data['bucket_31_60'] > 0:
            data['action'] = "Monitor Stock"
            data['action_class'] = "text-info"
        else:
            data['action'] = "Normal Procurement"
            data['action_class'] = "text-success"
            
        aging_data.append(data)
        
    # Sort by product name
    aging_data.sort(key=lambda x: x['product_name'])
    
    # Generate image
    from .utils import generate_stock_aging_image
    img = generate_stock_aging_image(aging_data, today.strftime("%d %b %Y"))
    
    # Return as response
    from io import BytesIO
    response = HttpResponse(content_type="image/png")
    img.save(response, "PNG")
    return response

