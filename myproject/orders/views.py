from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator
from sylvia.models import Vehicle, Dealer, Product, Order, OrderItem, Depot, AppSettings, MRN, OrderMRNImage
from sylvia.forms import VehicleForm, DealerForm, ProductForm, DepotForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg, Min, Max, Count, F, ExpressionWrapper, DurationField, Q
from datetime import timedelta
import json
import io
import calendar
import logging
from django.http import HttpResponse
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def check_audit_reminder():
    """Check if audit reminder should be shown (last 7 days of month)"""
    today = timezone.now().date()
    year = today.year
    month = today.month
    
    # Get last day of current month
    last_day_of_month = calendar.monthrange(year, month)[1]
    
    # Calculate if we're in the last 7 days
    days_until_end = last_day_of_month - today.day

    if days_until_end <= 7:  # Last 7 days of month (0-6 days remaining)
        return {
            'show_reminder': True,
            'days_remaining': days_until_end + 1,
            'month_name': calendar.month_name[month],
            'year': year
        }
    
    return {'show_reminder': False}

logger = logging.getLogger(__name__)

@login_required
def order_workflow(request):
    # Get all active entities
    vehicles = Vehicle.objects.filter(is_active=True)
    dealers = Dealer.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    depots = Depot.objects.filter(is_active=True)
    
    # Get vehicle_id from URL parameter if provided
    selected_vehicle_id = request.GET.get('vehicle_id')
    selected_vehicle = None
    if selected_vehicle_id:
        try:
            selected_vehicle = Vehicle.objects.get(id=selected_vehicle_id, is_active=True)
        except Vehicle.DoesNotExist:
            selected_vehicle = None

    if request.method == 'POST':
        dealer_id = request.POST.get('dealer')
        vehicle_id = request.POST.get('vehicle')
        depot_id = request.POST.get('depot')
        order_date = request.POST.get('order_date')
        # Collect product quantities from form
        product_ids = []
        quantities = []
        for product in products:
            qty = request.POST.get(f'product_{product.id}')
            if qty:
                try:
                    qty_val = float(qty)
                except ValueError:
                    qty_val = 0
                if qty_val > 0:
                    product_ids.append(product.id)
                    quantities.append(qty_val)

        # Basic validation
        if dealer_id and vehicle_id and depot_id and product_ids and quantities and len(product_ids) == len(quantities):
            try:
                dealer = Dealer.objects.get(id=dealer_id)
                vehicle = Vehicle.objects.get(id=vehicle_id)
                depot = Depot.objects.get(id=depot_id)
                # Set order date with constant time (1 PM IST)
                if order_date:
                    import datetime
                    from django.utils import timezone as djtz
                    try:
                        # Parse date and set time to 1:00 PM (13:00)
                        order_date_obj = datetime.datetime.strptime(order_date, "%Y-%m-%d")
                        order_date_obj = order_date_obj.replace(hour=13, minute=0, second=0, microsecond=0)
                        order_date = djtz.make_aware(order_date_obj)
                    except Exception:
                        order_date = djtz.now()
                else:
                    order_date = djtz.now()
                order = Order.objects.create(
                    dealer=dealer,
                    vehicle=vehicle,
                    depot=depot,
                    order_date=order_date,
                )

                for pid, qty in zip(product_ids, quantities):
                    product = Product.objects.get(id=pid)
                    OrderItem.objects.create(order=order, product=product, quantity=qty)
                return redirect('order_list')
            except Exception as e:
                logger.error(f"Exception during order creation: {e}")
                return render(request, 'orders/order_workflow.html', {
                    'vehicles': vehicles,
                    'dealers': dealers,
                    'products': products,
                    'depots': depots,
                    'now': timezone.now(),
                    'today': timezone.now().date(),
                    'selected_vehicle': selected_vehicle,
                    'selected_vehicle_id': selected_vehicle_id,
                    'error': 'An error occurred while creating the order. Please try again.',
                })
        else:
            return render(request, 'orders/order_workflow.html', {
                'vehicles': vehicles,
                'dealers': dealers,
                'products': products,
                'depots': depots,
                'now': timezone.now(),
                'today': timezone.now().date(),
                'selected_vehicle': selected_vehicle,
                'selected_vehicle_id': selected_vehicle_id,
                'error': 'Please fill all required fields and enter at least one product quantity.',
            })

    context = {
        'vehicles': vehicles,
        'dealers': dealers,
        'products': products,
        'depots': depots,
        'now': timezone.now(),
        'today': timezone.now().date(),
        'selected_vehicle': selected_vehicle,
        'selected_vehicle_id': selected_vehicle_id,
    }
    return render(request, 'orders/order_workflow.html', context)

@login_required
def home(request):
    from datetime import date, timedelta
    from django.db.models import Q, Sum
    
    settings = {s.key: s.value for s in AppSettings.objects.all()}
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    # Worker-focused metrics - shows actual efforts regardless of order dates
    
    # 1. Orders entered today (actual data entry work done)
    orders_entered_today = Order.objects.filter(created_at__date=today).count()
    
    # 2. Workflow actions today (status progression work)
    mrn_created_today = Order.objects.filter(mrn_date=today).count()
    orders_billed_today = Order.objects.filter(updated_at__date=today, status='BILLED').count()
    
    # 3. This week's productivity (7-day rolling metrics)
    orders_entered_week = Order.objects.filter(created_at__date__gte=week_ago).count()
    orders_billed_week = Order.objects.filter(bill_date__gte=week_ago).count()
    total_quantity_week = Order.objects.filter(created_at__date__gte=week_ago).aggregate(
        total=Sum('order_items__quantity')
    )['total'] or 0
    
    # 4. Additional inspiring metrics
    dealers_served_today = Order.objects.filter(created_at__date=today).values('dealer').distinct().count()
    vehicles_loaded_today = Order.objects.filter(created_at__date=today).values('vehicle').distinct().count()

    # Check for audit reminder
    audit_reminder = check_audit_reminder()

    context = {
        'app_settings': {
            'site_title': settings.get('site_title', 'Move People ― Move Mountains'),
            'site_description': settings.get('site_description', 'Move People ― Move Mountains'),
        },
        'daily_reports': {
            'orders_entered': orders_entered_today,
            'mrn_created': mrn_created_today,
            'orders_billed': orders_billed_today,
            'dealers_served': dealers_served_today,
            'vehicles_loaded': vehicles_loaded_today,
        },
        'weekly_reports': {
            'orders_entered': orders_entered_week,
            'orders_billed': orders_billed_week,
            'total_quantity': round(float(total_quantity_week), 2) if total_quantity_week else 0,
        },
        'current_date': today,
        'audit_reminder': audit_reminder,
    }
    return render(request, 'home.html', context)

def login_view(request):
    settings = {s.key: s.value for s in AppSettings.objects.all()}
    context = {
        'app_settings': {
            'login_title': settings.get('login_title', 'Login'),
        }
    }
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('home')
        else:
            context['error'] = 'Invalid username or password.'
    return render(request, 'login.html', context)

def logout_view(request):
    auth_logout(request)
    return redirect('login')

@login_required
def order_detail(request, order_id):
    """View to display order details with MRN images"""
    order = get_object_or_404(Order, id=order_id)
    mrn = getattr(order, 'mrn', None)
    mrn_status = mrn.status if mrn else 'PENDING'
    
    context = {
        'order': order,
        'mrn_status': mrn_status,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def update_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    mrn = getattr(order, 'mrn', None)
    mrn_status = mrn.status if mrn else 'PENDING'
    invoice_date = order.bill_date
    mrn_date = order.mrn_date
    
    # Check if dealer is Anonymous
    is_dealer_anonymous = order.dealer.name.lower() == 'anonymous'
    dealers = None
    if is_dealer_anonymous:
        dealers = Dealer.objects.filter(is_active=True).exclude(name__iexact='anonymous')
    
    # Get available products for adding to order
    current_product_ids = order.order_items.values_list('product_id', flat=True)
    available_products = Product.objects.filter(is_active=True).exclude(id__in=current_product_ids)
    
    if request.method == 'POST':
        try:
            # Handle status updates (existing functionality)
            new_mrn_status = request.POST.get('mrn_status')
            new_invoice_date = request.POST.get('invoice_date')
            new_mrn_date = request.POST.get('mrn_date')
            new_dealer_id = request.POST.get('dealer_id')
            
            # Update dealer if Anonymous and new dealer selected
            if is_dealer_anonymous and new_dealer_id:
                try:
                    new_dealer = Dealer.objects.get(id=new_dealer_id, is_active=True)
                    order.dealer = new_dealer
                except Dealer.DoesNotExist:
                    pass
            
            # Handle product updates (quantity only - no prices)
            products_to_update = {}
            existing_items = {item.product.id: item for item in order.order_items.all()}
            
            # Get products that should remain (exist in DOM)
            existing_product_ids = set()
            for key in request.POST.keys():
                if key.startswith('existing_product_'):
                    try:
                        product_id = int(key.split('_')[2])
                        existing_product_ids.add(product_id)
                    except (ValueError, IndexError):
                        continue
            
            # Process all product quantity form data
            for key, value in request.POST.items():
                if key.startswith('product_') and key.endswith('_quantity'):
                    parts = key.split('_')
                    if len(parts) >= 3:
                        try:
                            product_id = int(parts[1])
                            quantity = float(value) if value else 0
                            products_to_update[product_id] = quantity
                        except (ValueError, TypeError):
                            continue
            
            # First, remove products that are no longer in the DOM
            for product_id, item in existing_items.items():
                if product_id not in existing_product_ids and product_id not in products_to_update:
                    item.delete()
            
            # Update existing products and add new products
            for product_id, quantity in products_to_update.items():
                if product_id in existing_items and product_id in existing_product_ids:
                    # Update existing product that's still in DOM
                    item = existing_items[product_id]
                    
                    if quantity <= 0:
                        # Remove item if quantity is 0 or negative
                        item.delete()
                    else:
                        item.quantity = quantity
                        item.save()
                elif product_id not in existing_items:
                    # This is a new product to add
                    if quantity > 0:  # Only add if quantity is positive
                        try:
                            product = Product.objects.get(id=product_id, is_active=True)
                            OrderItem.objects.create(
                                order=order,
                                product=product,
                                quantity=quantity
                                # No unit_price since we're not handling prices
                            )
                        except Product.DoesNotExist:
                            logger.warning(f"Attempted to add non-existent product ID {product_id} to order {order.order_number}")
                            continue
            
            # Check if there are any remaining order items
            remaining_items = OrderItem.objects.filter(order=order).count()
            if remaining_items == 0:
                # Add error message or prevent saving
                logger.warning(f"Attempted to save order {order.order_number} with no products")
                context = {
                    'order': order,
                    'mrn_status': mrn_status,
                    'invoice_date': invoice_date,
                    'mrn_date': mrn_date,
                    'is_dealer_anonymous': is_dealer_anonymous,
                    'dealers': dealers,
                    'available_products': available_products,
                    'error': 'Order must have at least one product with a positive quantity.',
                }
                return render(request, 'orders/update_order.html', context)
            
            # Update MRN status and MRN date
            if mrn:
                if new_mrn_status:
                    mrn.status = new_mrn_status
                if new_mrn_date:
                    mrn.mrn_date = new_mrn_date
                mrn.save()
            elif new_mrn_status:
                mrn = MRN.objects.create(order=order, status=new_mrn_status, mrn_date=new_mrn_date)
            
            # Update order status if MRN approved
            if new_mrn_status == 'APPROVED':
                order.status = 'MRN_CREATED'
            
            # Update MRN date in Order
            if new_mrn_date:
                order.mrn_date = new_mrn_date
            
            # Update invoice date and status
            if new_invoice_date:
                order.bill_date = new_invoice_date
                order.status = 'BILLED'
            
            order.save()
            
            return redirect('order_list')
            
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {e}")
            context = {
                'order': order,
                'mrn_status': mrn_status,
                'invoice_date': invoice_date,
                'mrn_date': mrn_date,
                'is_dealer_anonymous': is_dealer_anonymous,
                'dealers': dealers,
                'available_products': available_products,
                'error': 'An error occurred while updating the order. Please try again.',
            }
            return render(request, 'orders/update_order.html', context)
    
    context = {
        'order': order,
        'mrn_status': mrn_status,
        'invoice_date': invoice_date,
        'mrn_date': mrn_date,
        'is_dealer_anonymous': is_dealer_anonymous,
        'dealers': dealers,
        'available_products': available_products,
    }
    return render(request, 'orders/update_order.html', context)

@login_required
def analytics(request):
    from sylvia.models import Order, Dealer
    from django.db.models import Sum
    from datetime import date
    import random
    
    now = timezone.now()
    today = date.today()
    orders = Order.objects.all()

    # Time between Order, MRN, Billing
    orders_with_dates = orders.exclude(mrn_date=None).exclude(bill_date=None)
    order_to_mrn = ExpressionWrapper(F('mrn_date') - F('order_date'), output_field=DurationField())
    mrn_to_bill = ExpressionWrapper(F('bill_date') - F('mrn_date'), output_field=DurationField())
    order_to_bill = ExpressionWrapper(F('bill_date') - F('order_date'), output_field=DurationField())

    time_stats = orders_with_dates.aggregate(
        avg_order_to_mrn=Avg(order_to_mrn),
        avg_mrn_to_bill=Avg(mrn_to_bill),
        avg_order_to_bill=Avg(order_to_bill),
        min_order_to_mrn=Min(order_to_mrn),
        max_order_to_mrn=Max(order_to_mrn),
        min_mrn_to_bill=Min(mrn_to_bill),
        max_mrn_to_bill=Max(mrn_to_bill),
        min_order_to_bill=Min(order_to_bill),
        max_order_to_bill=Max(order_to_bill),
    )



    # PROACTIVE FEATURE 2: Daily Dealer Contact Recommendations (Enhanced with Active/Dormant Mix)
    active_dealers = Dealer.objects.filter(is_active=True)
    active_recommendations = []
    dormant_recommendations = []
    
    for dealer in active_dealers:
        dealer_orders = orders.filter(dealer=dealer)
        
        # Calculate order history metrics
        last_30_days = dealer_orders.filter(order_date__gte=now - timedelta(days=30))
        
        monthly_orders = last_30_days.count()
        total_quantity_month = last_30_days.aggregate(
            total=Sum('order_items__quantity')
        )['total'] or 0
        
        # Get most ordered products - Alternative approach for better reliability
        from collections import defaultdict
        product_summary = defaultdict(float)
        
        # Aggregate product quantities manually for better control
        for order in dealer_orders:
            for item in order.order_items.all():
                product_summary[item.product.name] += float(item.quantity)
        
        # Convert to sorted list of tuples (product_name, total_quantity)
        popular_products = sorted(product_summary.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Also create a simple string summary for fallback
        product_summary_text = ", ".join([f"{name} ({qty:.0f}MT)" for name, qty in popular_products]) if popular_products else "No order history"
        
        # Calculate days since last order
        last_order = dealer_orders.order_by('-order_date').first()
        days_since_last_order = (now.date() - last_order.order_date.date()).days if last_order else 999
        
        # Calculate monthly frequency (orders per month over last 6 months)
        six_months_ago = now - timedelta(days=180)
        six_month_orders = dealer_orders.filter(order_date__gte=six_months_ago).count()
        monthly_frequency = round(six_month_orders / 6, 1) if six_month_orders > 0 else 0
        
        # Define dealer status: dormant if no orders in last 30-60 days
        is_dormant = days_since_last_order > 35 or (monthly_frequency > 0 and monthly_orders == 0)
        
        # Scoring logic for recommendation priority
        score = 0
        
        if is_dormant:
            # Dormant dealer scoring - higher priority for re-engagement
            if monthly_frequency > 1:  # Was a regular customer
                score += 15
            elif monthly_frequency > 0.5:  # Was semi-regular
                score += 12
            elif six_month_orders > 0:  # Had some orders historically
                score += 8
            else:  # Completely new or very old customer
                score += 5
            
            # Boost for high historical volume
            if dealer_orders.aggregate(total=Sum('order_items__quantity'))['total'] or 0 > 200:
                score += 5
        else:
            # Active dealer scoring - maintain relationships
            if monthly_frequency > 1 and days_since_last_order > 15:
                score += 10
            elif monthly_frequency > 0.5 and days_since_last_order > 20:
                score += 8
            elif days_since_last_order > 25:
                score += 6
            
            # Higher score for high-volume active dealers
            if total_quantity_month > 100:
                score += 5
            elif total_quantity_month > 50:
                score += 3
        
        # Slight randomization to vary recommendations daily
        random.seed(today.toordinal() + dealer.id)  # Consistent per day per dealer
        score += random.randint(1, 3)
        
        if score >= 5:  # Only recommend dealers with meaningful scores
            dealer_data = {
                'dealer': dealer,
                'score': score,
                'monthly_orders': monthly_orders,
                'monthly_frequency': monthly_frequency,
                'total_quantity_month': round(float(total_quantity_month), 2),
                'days_since_last_order': days_since_last_order,
                'popular_products': popular_products,  # List of tuples (name, quantity)
                'product_summary_text': product_summary_text,  # Simple string fallback
                'last_order_date': last_order.order_date.date() if last_order else None,
                'is_dormant': is_dormant,
                'dealer_status': 'Dormant' if is_dormant else 'Active',
            }
            
            if is_dormant:
                dormant_recommendations.append(dealer_data)
            else:
                active_recommendations.append(dealer_data)
    
    # Sort both lists by score
    active_recommendations.sort(key=lambda x: -x['score'])
    dormant_recommendations.sort(key=lambda x: -x['score'])
    
    # Mix recommendations: ensure at least 1 dormant dealer if available
    daily_dealer_recommendations = []
    
    # Add top dormant dealer first (if available)
    if dormant_recommendations:
        daily_dealer_recommendations.append(dormant_recommendations[0])
    
    # Add active dealers to fill remaining slots
    remaining_slots = 3 - len(daily_dealer_recommendations)
    daily_dealer_recommendations.extend(active_recommendations[:remaining_slots])
    
    # If we still have slots and more dormant dealers, add them
    if len(daily_dealer_recommendations) < 3 and len(dormant_recommendations) > 1:
        remaining_slots = 3 - len(daily_dealer_recommendations)
        daily_dealer_recommendations.extend(dormant_recommendations[1:1+remaining_slots])
    
    # Final sort by score to maintain priority order
    daily_dealer_recommendations.sort(key=lambda x: -x['score'])

    # Dealer-wise weekly/monthly stats
    dealer_stats = []
    for dealer in Dealer.objects.all():
        dealer_orders = orders.filter(dealer=dealer)
        weekly = dealer_orders.filter(order_date__gte=now-timedelta(days=7)).count()
        monthly = dealer_orders.filter(order_date__gte=now-timedelta(days=30)).count()
        avg_order_to_mrn = dealer_orders.exclude(mrn_date=None).aggregate(avg=Avg(order_to_mrn))['avg']
        avg_mrn_to_bill = dealer_orders.exclude(mrn_date=None).exclude(bill_date=None).aggregate(avg=Avg(mrn_to_bill))['avg']
        dealer_stats.append({
            'dealer_id': dealer.id,
            'dealer': dealer.name,
            'weekly_orders': weekly,
            'monthly_orders': monthly,
            'avg_order_to_mrn': avg_order_to_mrn,
            'avg_mrn_to_bill': avg_mrn_to_bill,
        })

    # Longest pending dealers (orders with no MRN or bill date)
    pending_orders = orders.filter(mrn_date=None) | orders.filter(bill_date=None)
    pending_dealers = pending_orders.values('dealer__name').annotate(
        pending_count=Count('id'),
        oldest_order=Min('order_date')
    ).order_by('-pending_count', 'oldest_order')[:10]

    # Additional analytics
    product_stats = orders.values('order_items__product__name').annotate(
        total_orders=Count('id'),
        avg_quantity=Avg('order_items__quantity')
    ).order_by('-total_orders')

    depot_stats = orders.values('depot__name').annotate(
        total_orders=Count('id')
    ).order_by('-total_orders')

    completed_orders = orders.filter(status='BILLED').count()
    mrn_pending_orders = orders.filter(status='PENDING').count()
    total_orders = orders.count()
    percent_completed = (completed_orders / total_orders * 100) if total_orders else 0

    context = {
        'time_stats': time_stats,
        'dealer_stats': dealer_stats,
        'mrn_created_orders': mrn_pending_orders,
        'pending_dealers': pending_dealers,
        'product_stats': product_stats,
        'depot_stats': depot_stats,
        'percent_completed': percent_completed,
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        # New proactive features
        'daily_dealer_recommendations': daily_dealer_recommendations,
        'today': today,
        'months': [calendar.month_name[i] for i in range(1, 13)],  # For month filter dropdown
    }
    return render(request, 'orders/analytics.html', context)

@login_required
def export_analytics(request):
    # Get filters from GET params
    dealer_id = request.GET.get('dealer')
    status = request.GET.get('status')
    month = request.GET.get('month')
    year = request.GET.get('year')
    export_format = request.GET.get('format', 'excel')

    orders = Order.objects.all()
    if dealer_id:
        orders = orders.filter(dealer_id=dealer_id)
    if status and status != 'ALL':
        orders = orders.filter(status=status)
    if month and year:
        orders = orders.filter(order_date__month=int(month), order_date__year=int(year))

    # Prepare data for export
    data = []
    for order in orders:
        data.append({
            'Order Number': order.order_number,
            'Dealer': order.dealer.name,
            'Vehicle': order.vehicle.truck_number,
            'Depot': order.depot.name if order.depot else '',
            'Order Date': order.order_date.strftime('%Y-%m-%d'),
            'MRN Date': order.mrn_date.strftime('%Y-%m-%d') if order.mrn_date else '',
            'Invoice Date': order.bill_date.strftime('%Y-%m-%d') if order.bill_date else '',
            'Status': order.status,
            'Product Types': ', '.join([item.product.name for item in order.order_items.all()]),
            'Total Quantity': order.get_total_quantity(),
        })

    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Orders')
        output.seek(0)
        response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=orders_export.xlsx'
        return response
    elif export_format == 'pdf':
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
        elements = []
        brand_name = "Shyam Distributors"
        brand_desc = "CFA Garhwa and Palamu"
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f'<b>{brand_name}</b>', styles['Title']))
        elements.append(Paragraph(brand_desc, styles['Normal']))
        elements.append(Spacer(1, 18))
        if data:
            headers = [k for k in data[0].keys() if k != 'Order Number']
            table_data = [headers]
            for row in data:
                table_data.append([str(row[h]) for h in headers])
            from reportlab.lib.units import inch
            max_table_width = 7.5 * inch
            col_count = len(headers)
            # Assign proportional widths (Product Types gets more)
            base_width = max_table_width / col_count
            col_widths = [base_width for _ in headers]
            if 'Product Types' in headers:
                idx = headers.index('Product Types')
                col_widths[idx] = base_width * 1.5
                # Reduce other columns
                for i in range(len(col_widths)):
                    if i != idx:
                        col_widths[i] = base_width * 0.85
            # Word wrap for long cells
            from reportlab.platypus import Paragraph
            from reportlab.lib.styles import ParagraphStyle
            cell_style = ParagraphStyle('cell', fontName='Helvetica', fontSize=8, leading=10)
            header_style = ParagraphStyle('header', fontName='Helvetica-Bold', fontSize=9, leading=11)
            table_data_wrapped = [[Paragraph(h, header_style) for h in headers]]
            for row in data:
                table_data_wrapped.append([Paragraph(str(row[h]), cell_style) for h in headers])
            table = Table(table_data_wrapped, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#222222')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,0), 9),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('LEFTPADDING', (0,0), (-1,-1), 3),
                ('RIGHTPADDING', (0,0), (-1,-1), 3),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph('No data available.', styles['Normal']))
        elements.append(Spacer(1, 24))
        from datetime import datetime
        gen_date = datetime.now().strftime('%d %B %Y, %I:%M %p')
        elements.append(Paragraph(f'<i>Generated on: {gen_date}</i>', styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        filename = f"orders_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    else:
        return HttpResponse('Invalid format', status=400)


@login_required
def add_vehicle(request):
    """View to add a new vehicle"""
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.created_by = request.user
            vehicle.save()
            return redirect('vehicle_list')
    else:
        form = VehicleForm()
    
    context = {
        'form': form,
        'title': 'Add Vehicle',
        'action': 'Add'
    }
    return render(request, 'vehicles/vehicle_form.html', context)


@login_required
def edit_vehicle(request, vehicle_id):
    """View to edit an existing vehicle"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            return redirect('vehicle_list')
    else:
        form = VehicleForm(instance=vehicle)
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'title': 'Edit Vehicle',
        'action': 'Update'
    }
    return render(request, 'vehicles/vehicle_form.html', context)


@login_required
def vehicle_list(request):
    """View to list all vehicles with search and filter options"""
    vehicles = Vehicle.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        vehicles = vehicles.filter(
            Q(truck_number__icontains=search_query) |
            Q(owner_name__icontains=search_query) |
            Q(driver_name__icontains=search_query)
        )
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        vehicles = vehicles.filter(is_active=True)
    elif status_filter == 'inactive':
        vehicles = vehicles.filter(is_active=False)
    
    # Filter by vehicle type
    type_filter = request.GET.get('type', '')
    if type_filter:
        vehicles = vehicles.filter(vehicle_type=type_filter)
    
    # Calculate statistics (before pagination)
    total_vehicles = vehicles.count()
    active_vehicles = vehicles.filter(is_active=True).count()
    total_capacity = sum(vehicle.capacity for vehicle in vehicles)
    avg_capacity = total_capacity / total_vehicles if total_vehicles > 0 else 0
    
    # Pagination
    paginator = Paginator(vehicles, 15)  # Show 15 vehicles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'vehicles': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'search_query': search_query,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'vehicle_types': Vehicle._meta.get_field('vehicle_type').choices,
        'stats': {
            'total_vehicles': total_vehicles,
            'active_vehicles': active_vehicles,
            'total_capacity': total_capacity,
            'avg_capacity': avg_capacity,
        }
    }
    return render(request, 'vehicles/vehicle_list.html', context)


@login_required
def delete_vehicle(request, vehicle_id):
    """View to delete a vehicle"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    
    if request.method == 'POST':
        vehicle.delete()
        return redirect('vehicle_list')
    
    context = {
        'vehicle': vehicle,
        'title': 'Delete Vehicle'
    }
    return render(request, 'vehicles/vehicle_confirm_delete.html', context)


@login_required
def dealer_list(request):
    """View to list all dealers with search and filter options"""
    dealers = Dealer.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        dealers = dealers.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(city__icontains=search_query)
        )
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        dealers = dealers.filter(is_active=True)
    elif status_filter == 'inactive':
        dealers = dealers.filter(is_active=False)
    
    # Calculate statistics (before pagination)
    total_dealers = dealers.count()
    active_dealers = dealers.filter(is_active=True).count()
    total_credit_limit = sum(dealer.credit_limit for dealer in dealers)
    avg_credit_limit = total_credit_limit / total_dealers if total_dealers > 0 else 0
    
    # Pagination
    paginator = Paginator(dealers, 15)  # Show 15 dealers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'dealers': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'search_query': search_query,
        'status_filter': status_filter,
        'stats': {
            'total_dealers': total_dealers,
            'active_dealers': active_dealers,
            'total_credit_limit': total_credit_limit,
            'avg_credit_limit': avg_credit_limit,
        }
    }
    return render(request, 'dealers/dealer_list.html', context)


@login_required
def add_dealer(request):
    """View to add a new dealer"""
    if request.method == 'POST':
        form = DealerForm(request.POST)
        if form.is_valid():
            dealer = form.save(commit=False)
            dealer.created_by = request.user
            dealer.save()
            return redirect('dealer_list')
    else:
        form = DealerForm()
    
    context = {
        'form': form,
        'title': 'Add Dealer',
        'action': 'Add'
    }
    return render(request, 'dealers/dealer_form.html', context)


@login_required
def edit_dealer(request, dealer_id):
    """View to edit an existing dealer"""
    dealer = get_object_or_404(Dealer, id=dealer_id)
    
    if request.method == 'POST':
        form = DealerForm(request.POST, instance=dealer)
        if form.is_valid():
            form.save()
            return redirect('dealer_list')
    else:
        form = DealerForm(instance=dealer)
    
    context = {
        'form': form,
        'dealer': dealer,
        'title': 'Edit Dealer',
        'action': 'Update'
    }
    return render(request, 'dealers/dealer_form.html', context)


@login_required
def delete_dealer(request, dealer_id):
    """View to delete a dealer"""
    dealer = get_object_or_404(Dealer, id=dealer_id)
    
    if request.method == 'POST':
        dealer.delete()
        return redirect('dealer_list')
    
    context = {
        'dealer': dealer,
        'title': 'Delete Dealer'
    }
    return render(request, 'dealers/dealer_confirm_delete.html', context)


@login_required
def add_product(request):
    """View to add a new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Add Product',
        'action': 'Add'
    }
    return render(request, 'products/product_form.html', context)


@login_required
def add_depot(request):
    """View to add a new depot"""
    if request.method == 'POST':
        form = DepotForm(request.POST)
        if form.is_valid():
            depot = form.save(commit=False)
            depot.created_by = request.user
            depot.save()
            return redirect('depot_list')
    else:
        form = DepotForm()
    
    context = {
        'form': form,
        'title': 'Add Depot',
        'action': 'Add'
    }
    return render(request, 'depots/depot_form.html', context)


