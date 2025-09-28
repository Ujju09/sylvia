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
            new_remarks = request.POST.get('remarks')
            
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
            
            # Update remarks
            if new_remarks is not None:
                order.remarks = new_remarks
            
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
    from sylvia.models import Order
    from datetime import date, datetime

    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    orders = None
    start_date = None
    end_date = None

    # If date range is provided, filter orders
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Filter orders by date range (using order_date)
            orders = Order.objects.filter(
                order_date__date__gte=start_date,
                order_date__date__lte=end_date
            ).select_related('dealer', 'vehicle', 'depot').prefetch_related('order_items__product').order_by('order_date')

        except ValueError:
            # Invalid date format
            start_date = end_date = None
            orders = None

    context = {
        'orders': orders,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'orders/analytics.html', context)

@login_required
def export_analytics(request):
    from datetime import datetime

    # Get date range parameters for register
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not start_date_str or not end_date_str:
        return HttpResponse('Date range is required for order register', status=400)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return HttpResponse('Invalid date format', status=400)

    # Filter orders by date range
    orders = Order.objects.filter(
        order_date__date__gte=start_date,
        order_date__date__lte=end_date
    ).select_related('dealer', 'vehicle', 'depot').prefetch_related('order_items__product').order_by('order_date')

    # Prepare data for register format
    data = []
    serial_number = 1

    for order in orders:
        # Apply blanking rules
        dealer_name = ""
        if order.dealer.name.lower() != "anonymous" and order.depot.name != "Unknown Depot":
            dealer_name = order.dealer.name

        mrn_date = ""
        if order.mrn_date:
            mrn_date = order.mrn_date.strftime('%d-%m-%Y')

        billing_date = ""
        if order.bill_date:
            billing_date = order.bill_date.strftime('%d-%m-%Y')

        # Combine all products for this order
        products = ', '.join([item.product.name for item in order.order_items.all()])
        total_quantity = order.get_total_quantity()

        data.append({
            'S.No.': serial_number,
            'Order Date': order.order_date.strftime('%d-%m-%Y'),
            'Truck Number': order.vehicle.truck_number,
            'Product': products,
            'Qty (MT)': f"{total_quantity:.2f}" if total_quantity else "0.00",
            'Dealer Name': dealer_name,
            'MRN Date': mrn_date,
            'Billing Date': billing_date,
        })
        serial_number += 1

    # Generate PDF register
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch

    buffer = io.BytesIO()
    # Use landscape orientation for better table fit
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    elements = []

    # Company header
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=6,
        alignment=1  # Center alignment
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        alignment=1  # Center alignment
    )

    elements.append(Paragraph('<b>SHYAM DISTRIBUTORS</b>', title_style))
    elements.append(Paragraph('CFA Garhwa and Palamu', subtitle_style))
    elements.append(Paragraph('<b>ORDER REGISTER</b>', subtitle_style))

    # Date range info
    date_range_text = f"From: {start_date.strftime('%d %B %Y')} &nbsp;&nbsp;&nbsp; To: {end_date.strftime('%d %B %Y')}"
    elements.append(Paragraph(date_range_text, subtitle_style))
    elements.append(Spacer(1, 20))

    if data:
        # Prepare table data
        headers = ['S.No.', 'Order Date', 'Truck Number', 'Product', 'Qty (MT)', 'Dealer Name', 'MRN Date', 'Billing Date']
        table_data = [headers]

        for row in data:
            table_row = [
                str(row['S.No.']),
                row['Order Date'],
                row['Truck Number'],
                row['Product'],
                row['Qty (MT)'],
                row['Dealer Name'] if row['Dealer Name'] else '_____________',
                row['MRN Date'] if row['MRN Date'] else '_____________',
                row['Billing Date'] if row['Billing Date'] else '_____________'
            ]
            table_data.append(table_row)

        # Column widths optimized for landscape A4
        page_width = landscape(A4)[0] - (2 * 0.5 * inch)  # Total available width
        col_widths = [
            0.6*inch,   # S.No.
            0.9*inch,   # Order Date
            1.1*inch,   # Truck Number
            2.2*inch,   # Product
            0.8*inch,   # Qty (MT)
            1.5*inch,   # Dealer Name
            0.9*inch,   # MRN Date
            0.9*inch,   # Billing Date
        ]

        # Create table with styling optimized for printing
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8e8e8')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('TOPPADDING', (0,0), (-1,0), 8),

            # Data row styling
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),

            # Grid and borders
            ('GRID', (0,0), (-1,-1), 0.75, colors.black),
            ('LINEBELOW', (0,0), (-1,0), 1.5, colors.black),

            # Text alignment adjustments
            ('ALIGN', (0,0), (0,-1), 'CENTER'),    # S.No. center
            ('ALIGN', (1,0), (1,-1), 'CENTER'),    # Date center
            ('ALIGN', (2,0), (2,-1), 'CENTER'),    # Truck center
            ('ALIGN', (3,0), (3,-1), 'LEFT'),      # Product left
            ('ALIGN', (4,0), (4,-1), 'CENTER'),    # Qty center
            ('ALIGN', (5,0), (5,-1), 'LEFT'),      # Dealer left
            ('ALIGN', (6,0), (6,-1), 'CENTER'),    # MRN Date center
            ('ALIGN', (7,0), (7,-1), 'CENTER'),    # Billing Date center
        ]))

        elements.append(table)
    else:
        elements.append(Paragraph('No orders found in the selected date range.', styles['Normal']))

    # Footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666')
    )
    gen_date = datetime.now().strftime('%d %B %Y at %I:%M %p')
    elements.append(Paragraph(f'Generated on: {gen_date}', footer_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    # Response
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"order_register_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response


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


