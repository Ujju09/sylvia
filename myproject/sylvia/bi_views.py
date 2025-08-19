from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Sum, Avg, Q, F, Case, When, IntegerField, Max
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal
import calendar
from collections import defaultdict

from .models import (
    Order, OrderItem, Depot, Product, Vehicle, Dealer, MRN
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def executive_summary(request):
    """
    Executive Dashboard API - Main KPIs and overview metrics
    Query params: depot_id, start_date, end_date
    """
    # Parse query parameters
    depot_id = request.query_params.get('depot_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Base queryset
    orders = Order.objects.all()
    
    # Apply filters
    if depot_id and depot_id != 'all':
        try:
            depot_id = int(depot_id)
            orders = orders.filter(depot_id=depot_id)
        except (ValueError, TypeError):
            pass
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(order_date__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(order_date__date__lte=end_date)
        except ValueError:
            pass
    
    # Calculate KPIs
    total_orders = orders.count()
    
    # Stock orders (anonymous dealer)
    stock_orders = orders.filter(dealer__name__iexact='anonymous').count()
    regular_orders = total_orders - stock_orders
    
    # Total quantity billed (from order items)
    total_quantity = orders.aggregate(
        total=Sum('order_items__quantity')
    )['total'] or 0
    
    # Active vehicles count
    active_vehicles = Vehicle.objects.filter(is_active=True).count()
    
    # Vehicles with stock (carrying anonymous dealer orders)
    vehicles_with_stock = orders.filter(
        dealer__name__iexact='anonymous'
    ).values('vehicle').distinct().count()
    
    # Completion rate (billed orders / total orders)
    billed_orders = orders.filter(status='BILLED').count()
    completion_rate = (billed_orders / total_orders * 100) if total_orders > 0 else 0
    
    # Calculate month-over-month trends
    now = timezone.now().date()
    current_month_start = now.replace(day=1)
    
    # Previous month
    if current_month_start.month == 1:
        prev_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        prev_month_start = current_month_start.replace(month=current_month_start.month - 1)
    
    # Current month orders
    current_month_orders = orders.filter(
        order_date__date__gte=current_month_start,
        order_date__date__lt=now
    ).count()
    
    # Previous month orders
    prev_month_orders = orders.filter(
        order_date__date__gte=prev_month_start,
        order_date__date__lt=current_month_start
    ).count()
    
    # Calculate trends
    orders_mom = 0
    quantity_mom = 0
    
    if prev_month_orders > 0:
        orders_mom = ((current_month_orders - prev_month_orders) / prev_month_orders) * 100
    
    # Current month quantity
    current_month_qty = orders.filter(
        order_date__date__gte=current_month_start
    ).aggregate(total=Sum('order_items__quantity'))['total'] or 0
    
    # Previous month quantity
    prev_month_qty = orders.filter(
        order_date__date__gte=prev_month_start,
        order_date__date__lt=current_month_start
    ).aggregate(total=Sum('order_items__quantity'))['total'] or 0
    
    if prev_month_qty > 0:
        quantity_mom = ((float(current_month_qty) - float(prev_month_qty)) / float(prev_month_qty)) * 100
    
    # Determine efficiency trend
    efficiency_trend = "stable"
    if orders_mom > 5:
        efficiency_trend = "improving"
    elif orders_mom < -5:
        efficiency_trend = "declining"
    
    # Format date range for response
    date_range = "All time"
    if start_date and end_date:
        date_range = f"{start_date} to {end_date}"
    elif start_date:
        date_range = f"From {start_date}"
    elif end_date:
        date_range = f"Until {end_date}"
    
    depot_filter = "all"
    if depot_id and depot_id != 'all':
        try:
            depot = Depot.objects.get(id=depot_id)
            depot_filter = depot.name
        except Depot.DoesNotExist:
            pass
    
    return Response({
        "date_range": date_range,
        "depot_filter": depot_filter,
        "kpis": {
            "total_orders": total_orders,
            "stock_orders": stock_orders,
            "regular_orders": regular_orders,
            "total_quantity_billed": round(float(total_quantity), 2),
            "active_vehicles": active_vehicles,
            "vehicles_with_stock": vehicles_with_stock,
            "completion_rate": round(completion_rate, 1)
        },
        "trends": {
            "orders_month_over_month": round(orders_mom, 1),
            "quantity_month_over_month": round(quantity_mom, 1),
            "efficiency_trend": efficiency_trend
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_analytics(request):
    """
    Stock Management API - All stock-related analytics (anonymous dealer orders)
    Query params: depot_id, start_date, end_date, product_ids[]
    """
    # Parse query parameters
    depot_id = request.query_params.get('depot_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    product_ids = request.query_params.getlist('product_ids[]')
    
    # Base queryset for stock orders (anonymous dealer)
    stock_orders = Order.objects.filter(dealer__name__iexact='anonymous')
    
    # Apply filters
    if depot_id and depot_id != 'all':
        try:
            depot_id = int(depot_id)
            stock_orders = stock_orders.filter(depot_id=depot_id)
        except (ValueError, TypeError):
            pass
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            stock_orders = stock_orders.filter(order_date__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            stock_orders = stock_orders.filter(order_date__date__lte=end_date)
        except ValueError:
            pass
    
    if product_ids:
        try:
            product_ids = [int(pid) for pid in product_ids if pid.isdigit()]
            stock_orders = stock_orders.filter(order_items__product_id__in=product_ids).distinct()
        except (ValueError, TypeError):
            pass
    
    # Stock summary
    total_stock_orders = stock_orders.count()
    total_stock_quantity = stock_orders.aggregate(
        total=Sum('order_items__quantity')
    )['total'] or 0
    
    vehicles_carrying_stock = stock_orders.values('vehicle').distinct().count()
    avg_stock_per_vehicle = float(total_stock_quantity) / vehicles_carrying_stock if vehicles_carrying_stock > 0 else 0
    
    # Stock by depot
    stock_by_depot = []
    depot_stats = stock_orders.values('depot__id', 'depot__name').annotate(
        stock_orders=Count('id'),
        stock_quantity=Sum('order_items__quantity'),
        vehicles_count=Count('vehicle', distinct=True)
    ).order_by('-stock_quantity')
    
    total_quantity_float = float(total_stock_quantity) if total_stock_quantity > 0 else 0
    
    for depot_stat in depot_stats:
        percentage = (float(depot_stat['stock_quantity'] or 0) / total_quantity_float * 100) if total_quantity_float > 0 else 0
        stock_by_depot.append({
            "depot_id": depot_stat['depot__id'],
            "depot_name": depot_stat['depot__name'],
            "stock_orders": depot_stat['stock_orders'],
            "stock_quantity": round(float(depot_stat['stock_quantity'] or 0), 2),
            "vehicles_count": depot_stat['vehicles_count'],
            "percentage_of_total": round(percentage, 1)
        })
    
    # Stock by product
    stock_by_product = []
    product_stats = stock_orders.values('order_items__product__name').annotate(
        stock_quantity=Sum('order_items__quantity')
    ).order_by('-stock_quantity')[:10]  # Top 10 products
    
    for product_stat in product_stats:
        if product_stat['order_items__product__name']:
            percentage = (float(product_stat['stock_quantity'] or 0) / total_quantity_float * 100) if total_quantity_float > 0 else 0
            stock_by_product.append({
                "product_name": product_stat['order_items__product__name'],
                "stock_quantity": round(float(product_stat['stock_quantity'] or 0), 2),
                "percentage": round(percentage, 1)
            })
    
    # Vehicles with stock details
    vehicles_with_stock_details = []
    vehicle_stats = stock_orders.values(
        'vehicle__id', 'vehicle__truck_number', 'depot__name'
    ).annotate(
        stock_quantity=Sum('order_items__quantity'),
        last_updated=Max('updated_at')
    ).order_by('-stock_quantity')[:20]  # Top 20 vehicles
    
    for vehicle_stat in vehicle_stats:
        vehicles_with_stock_details.append({
            "vehicle_id": vehicle_stat['vehicle__id'],
            "truck_number": vehicle_stat['vehicle__truck_number'],
            "depot_name": vehicle_stat['depot__name'],
            "stock_quantity": round(float(vehicle_stat['stock_quantity'] or 0), 2),
            "last_updated": vehicle_stat['last_updated'].isoformat() if vehicle_stat['last_updated'] else None
        })
    
    return Response({
        "stock_summary": {
            "total_stock_orders": total_stock_orders,
            "total_stock_quantity": round(float(total_stock_quantity), 2),
            "vehicles_carrying_stock": vehicles_carrying_stock,
            "average_stock_per_vehicle": round(avg_stock_per_vehicle, 2)
        },
        "stock_by_depot": stock_by_depot,
        "stock_by_product": stock_by_product,
        "vehicles_with_stock": vehicles_with_stock_details
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def monthly_trends(request):
    """
    Monthly Trends API - Month-on-month analysis for charts and trends
    Query params: depot_id, granularity (monthly/weekly), months_back, include_stock
    """
    # Parse query parameters
    depot_id = request.query_params.get('depot_id')
    granularity = request.query_params.get('granularity', 'monthly')
    months_back = int(request.query_params.get('months_back', 12))
    include_stock = request.query_params.get('include_stock', 'true').lower() == 'true'
    
    # Base queryset
    orders = Order.objects.all()
    
    # Apply depot filter
    if depot_id and depot_id != 'all':
        try:
            depot_id = int(depot_id)
            orders = orders.filter(depot_id=depot_id)
        except (ValueError, TypeError):
            pass
    
    # Calculate date range
    now = timezone.now().date()
    start_date = now.replace(day=1) - timedelta(days=months_back * 30)
    orders = orders.filter(order_date__date__gte=start_date)
    
    # Generate monthly data
    quantity_billed_trends = []
    order_trends = []
    
    for i in range(months_back):
        # Calculate month start and end
        month_date = now.replace(day=1) - timedelta(days=i * 30)
        month_start = month_date.replace(day=1)
        
        # Calculate next month start
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)
        
        month_orders = orders.filter(
            order_date__date__gte=month_start,
            order_date__date__lt=next_month_start
        )
        
        # Total quantity for this month
        total_quantity = month_orders.aggregate(
            total=Sum('order_items__quantity')
        )['total'] or 0
        
        # Quantity by depot
        by_depot = []
        depot_quantities = month_orders.values('depot__name').annotate(
            quantity=Sum('order_items__quantity')
        ).order_by('-quantity')
        
        for depot_qty in depot_quantities:
            if depot_qty['depot__name']:
                by_depot.append({
                    "depot_name": depot_qty['depot__name'],
                    "quantity": round(float(depot_qty['quantity'] or 0), 2)
                })
        
        # Quantity by product
        by_product = []
        product_quantities = month_orders.values('order_items__product__name').annotate(
            quantity=Sum('order_items__quantity')
        ).order_by('-quantity')[:5]  # Top 5 products
        
        for product_qty in product_quantities:
            if product_qty['order_items__product__name']:
                by_product.append({
                    "product_name": product_qty['order_items__product__name'],
                    "quantity": round(float(product_qty['quantity'] or 0), 2)
                })
        
        quantity_billed_trends.append({
            "month": month_start.strftime('%Y-%m'),
            "total_quantity": round(float(total_quantity), 2),
            "by_depot": by_depot,
            "by_product": by_product
        })
        
        # Order trends
        total_orders = month_orders.count()
        stock_orders = month_orders.filter(dealer__name__iexact='anonymous').count() if include_stock else 0
        regular_orders = total_orders - stock_orders
        
        order_trends.append({
            "month": month_start.strftime('%Y-%m'),
            "total_orders": total_orders,
            "stock_orders": stock_orders if include_stock else 0,
            "regular_orders": regular_orders
        })
    
    # Reverse to show oldest first
    quantity_billed_trends.reverse()
    order_trends.reverse()
    
    # Depot performance over time
    depot_performance = []
    depots = Depot.objects.filter(is_active=True)
    
    for depot in depots:
        monthly_data = []
        depot_orders = orders.filter(depot=depot)
        
        for i in range(months_back):
            month_date = now.replace(day=1) - timedelta(days=i * 30)
            month_start = month_date.replace(day=1)
            
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1)
            
            month_depot_orders = depot_orders.filter(
                order_date__date__gte=month_start,
                order_date__date__lt=next_month_start
            )
            
            total_orders = month_depot_orders.count()
            total_quantity = month_depot_orders.aggregate(
                total=Sum('order_items__quantity')
            )['total'] or 0
            
            # Simple efficiency score based on completion rate
            billed_orders = month_depot_orders.filter(status='BILLED').count()
            efficiency_score = (billed_orders / total_orders * 100) if total_orders > 0 else 0
            
            monthly_data.append({
                "month": month_start.strftime('%Y-%m'),
                "orders": total_orders,
                "quantity": round(float(total_quantity), 2),
                "efficiency_score": round(efficiency_score, 1)
            })
        
        monthly_data.reverse()  # Oldest first
        
        # Only include depots with some activity
        if any(data['orders'] > 0 for data in monthly_data):
            depot_performance.append({
                "depot_name": depot.name,
                "monthly_data": monthly_data
            })
    
    return Response({
        "quantity_billed_trends": quantity_billed_trends,
        "order_trends": order_trends,
        "depot_performance": depot_performance
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def depot_analytics(request):
    """
    Depot Analytics API - All data categorized by depots for depot comparison
    Query params: start_date, end_date, include_stock
    """
    # Parse query parameters
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    include_stock = request.query_params.get('include_stock', 'true').lower() == 'true'
    
    # Base queryset
    orders = Order.objects.all()
    
    # Apply date filters
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(order_date__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(order_date__date__lte=end_date)
        except ValueError:
            pass
    
    # Get all active depots
    depots = Depot.objects.filter(is_active=True)
    depot_summary = []
    
    for depot in depots:
        depot_orders = orders.filter(depot=depot)
        
        # Basic counts
        total_orders = depot_orders.count()
        if not include_stock:
            stock_orders = 0
            regular_orders = total_orders
        else:
            stock_orders = depot_orders.filter(dealer__name__iexact='anonymous').count()
            regular_orders = total_orders - stock_orders
        
        # Total quantity
        total_quantity = depot_orders.aggregate(
            total=Sum('order_items__quantity')
        )['total'] or 0
        
        # Active vehicles for this depot
        active_vehicles = depot_orders.values('vehicle').distinct().count()
        
        # Completion rate
        billed_orders = depot_orders.filter(status='BILLED').count()
        completion_rate = (billed_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Top products for this depot
        top_products = []
        product_stats = depot_orders.values('order_items__product__name').annotate(
            quantity=Sum('order_items__quantity')
        ).order_by('-quantity')[:3]
        
        for product_stat in product_stats:
            if product_stat['order_items__product__name']:
                top_products.append({
                    "product_name": product_stat['order_items__product__name'],
                    "quantity": round(float(product_stat['quantity'] or 0), 2)
                })
        
        # Monthly performance (last 6 months)
        monthly_performance = []
        now = timezone.now().date()
        
        for i in range(6):
            month_date = now.replace(day=1) - timedelta(days=i * 30)
            month_start = month_date.replace(day=1)
            
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1)
            
            month_orders = depot_orders.filter(
                order_date__date__gte=month_start,
                order_date__date__lt=next_month_start
            )
            
            month_total_orders = month_orders.count()
            month_quantity = month_orders.aggregate(
                total=Sum('order_items__quantity')
            )['total'] or 0
            
            monthly_performance.append({
                "month": month_start.strftime('%Y-%m'),
                "orders": month_total_orders,
                "quantity": round(float(month_quantity), 2)
            })
        
        monthly_performance.reverse()  # Oldest first
        
        depot_summary.append({
            "depot_id": depot.id,
            "depot_name": depot.name,
            "total_orders": total_orders,
            "stock_orders": stock_orders if include_stock else 0,
            "regular_orders": regular_orders,
            "total_quantity": round(float(total_quantity), 2),
            "active_vehicles": active_vehicles,
            "completion_rate": round(completion_rate, 1),
            "top_products": top_products,
            "monthly_performance": monthly_performance
        })
    
    # Sort by total orders (descending)
    depot_summary.sort(key=lambda x: x['total_orders'], reverse=True)
    
    # Depot comparison matrix
    performance_matrix = []
    
    # Sort by different metrics for ranking
    orders_ranking = sorted(depot_summary, key=lambda x: x['total_orders'], reverse=True)
    quantity_ranking = sorted(depot_summary, key=lambda x: x['total_quantity'], reverse=True)
    efficiency_ranking = sorted(depot_summary, key=lambda x: x['completion_rate'], reverse=True)
    
    for depot in depot_summary:
        depot_name = depot['depot_name']
        
        # Find ranks
        orders_rank = next(i + 1 for i, d in enumerate(orders_ranking) if d['depot_name'] == depot_name)
        quantity_rank = next(i + 1 for i, d in enumerate(quantity_ranking) if d['depot_name'] == depot_name)
        efficiency_rank = next(i + 1 for i, d in enumerate(efficiency_ranking) if d['depot_name'] == depot_name)
        
        performance_matrix.append({
            "depot_name": depot_name,
            "orders_rank": orders_rank,
            "quantity_rank": quantity_rank,
            "efficiency_rank": efficiency_rank
        })
    
    return Response({
        "depot_summary": depot_summary,
        "depot_comparison": {
            "performance_matrix": performance_matrix
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def operations_live(request):
    """
    Real-time Operations API - Live operational data for real-time dashboard updates
    """
    today = timezone.now().date()
    now = timezone.now()
    
    # Today's metrics
    today_orders = Order.objects.filter(created_at__date=today)
    
    orders_created = today_orders.count()
    stock_orders_created = today_orders.filter(dealer__name__iexact='anonymous').count()
    
    # MRN completed today (orders with MRN date set to today)
    mrn_completed = Order.objects.filter(mrn_date=today).count()
    
    # Orders billed today
    orders_billed = Order.objects.filter(bill_date=today).count()
    
    # Vehicles loaded today (distinct vehicles from today's orders)
    vehicles_loaded = today_orders.values('vehicle').distinct().count()
    
    # Pending actions
    pending_mrn = Order.objects.filter(
        Q(mrn_date__isnull=True) | Q(status='PENDING')
    ).count()
    
    pending_billing = Order.objects.filter(
        mrn_date__isnull=False,
        bill_date__isnull=True
    ).count()
    
    # Overdue orders (older than 7 days without MRN)
    week_ago = now - timedelta(days=7)
    overdue_orders = Order.objects.filter(
        order_date__lt=week_ago,
        mrn_date__isnull=True
    ).count()
    
    # Active vehicles with stock details
    active_vehicles = []
    stock_vehicle_orders = Order.objects.filter(
        dealer__name__iexact='anonymous',
        order_date__date__gte=today - timedelta(days=30)  # Last 30 days
    ).select_related('vehicle', 'depot').prefetch_related('order_items')
    
    # Group by vehicle
    vehicle_stock_map = defaultdict(lambda: {
        'depot': '',
        'quantity': 0,
        'truck_number': ''
    })
    
    for order in stock_vehicle_orders:
        vehicle_key = order.vehicle.id
        total_quantity = sum(item.quantity for item in order.order_items.all())
        
        vehicle_stock_map[vehicle_key]['truck_number'] = order.vehicle.truck_number
        vehicle_stock_map[vehicle_key]['depot'] = order.depot.name if order.depot else 'Unknown'
        vehicle_stock_map[vehicle_key]['quantity'] += float(total_quantity)
    
    # Convert to list format
    for vehicle_id, data in list(vehicle_stock_map.items())[:20]:  # Limit to 20 vehicles
        active_vehicles.append({
            "truck_number": data['truck_number'],
            "depot": data['depot'],
            "status": "carrying_stock",
            "quantity": round(data['quantity'], 2)
        })
    
    # Sort by quantity (descending)
    active_vehicles.sort(key=lambda x: x['quantity'], reverse=True)
    
    return Response({
        "today_metrics": {
            "orders_created": orders_created,
            "stock_orders_created": stock_orders_created,
            "mrn_completed": mrn_completed,
            "orders_billed": orders_billed,
            "vehicles_loaded": vehicles_loaded
        },
        "pending_actions": {
            "pending_mrn": pending_mrn,
            "pending_billing": pending_billing,
            "overdue_orders": overdue_orders
        },
        "active_vehicles": active_vehicles
    })