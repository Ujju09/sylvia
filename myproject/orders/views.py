from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from sylvia.models import Vehicle, Dealer, Product, Order, OrderItem, Depot, AppSettings, MRN
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Avg, Min, Max, Count, F, ExpressionWrapper, DurationField
from datetime import timedelta
import json
import io
import calendar
from django.http import HttpResponse
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

@login_required
def order_workflow(request):
    # For prototype, just pass all vehicles, dealers, products
    vehicles = Vehicle.objects.filter(is_active=True)
    dealers = Dealer.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    depots = Depot.objects.filter(is_active=True)

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
                # Make order_date timezone-aware if needed
                if order_date:
                    import datetime
                    from django.utils import timezone as djtz
                    if isinstance(order_date, str):
                        try:
                            order_date_obj = datetime.datetime.strptime(order_date, "%Y-%m-%d %H:%M")
                            order_date = djtz.make_aware(order_date_obj)
                        except Exception as dt_err:
                            print(f"[ERROR] Failed to parse order_date: {dt_err}")
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
                print(f"[ERROR] Exception during order creation: {e}")
                return render(request, 'orders/order_workflow.html', {
                    'vehicles': vehicles,
                    'dealers': dealers,
                    'products': products,
                    'depots': depots,
                    'now': timezone.now(),
                    'today': timezone.now().date(),
                    'error': f'Error: {e}',
                })
        else:
            print("[ERROR] Validation failed. Missing required fields or no product quantities entered.")
            return render(request, 'orders/order_workflow.html', {
                'vehicles': vehicles,
                'dealers': dealers,
                'products': products,
                'depots': depots,
                'now': timezone.now(),
                'today': timezone.now().date(),
                'error': 'Please fill all required fields and enter at least one product quantity.',
            })

    context = {
        'vehicles': vehicles,
        'dealers': dealers,
        'products': products,
        'depots': depots,
        'now': timezone.now(),
        'today': timezone.now().date(),
    }
    return render(request, 'orders/order_workflow.html', context)

@login_required
def home(request):
    settings = {s.key: s.value for s in AppSettings.objects.all()}
    # Get dealer locations

    context = {
        'app_settings': {
            'site_title': settings.get('site_title', 'Move People ― Move Mountains'),
            'site_description': settings.get('site_description', 'Move People ― Move Mountains'),
        },
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
def update_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    mrn = getattr(order, 'mrn', None)
    mrn_status = mrn.status if mrn else 'PENDING'
    invoice_date = order.bill_date
    mrn_date = order.mrn_date
    if request.method == 'POST':
        new_mrn_status = request.POST.get('mrn_status')
        new_invoice_date = request.POST.get('invoice_date')
        new_mrn_date = request.POST.get('mrn_date')
        # Update MRN status and MRN date
        if mrn:
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
    context = {
        'order': order,
        'mrn_status': mrn_status,
        'invoice_date': invoice_date,
        'mrn_date': mrn_date,
    }
    return render(request, 'orders/update_order.html', context)

@login_required
def analytics(request):
    from sylvia.models import Order, Dealer
    now = timezone.now()
    orders = Order.objects.all()

    # Time between Order, MRN, Billing
    orders_with_dates = orders.exclude(mrn_date=None).exclude(bill_date=None)
    order_to_mrn = ExpressionWrapper(F('mrn_date') - F('order_date'), output_field=DurationField())
    mrn_to_bill = ExpressionWrapper(F('bill_date') - F('mrn_date'), output_field=DurationField(
    ))
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




