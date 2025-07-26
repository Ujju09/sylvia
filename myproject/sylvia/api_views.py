from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth.models import User

from .models import (
    Depot, Product, Dealer, Vehicle, Order, OrderItem, 
    MRN, Invoice, AuditLog, AppSettings, NotificationTemplate, DealerContext
)
from .serializers import (
    DepotSerializer, ProductSerializer, DealerSerializer, VehicleSerializer,
    OrderSerializer, OrderCreateSerializer, OrderItemSerializer, MRNSerializer,
    InvoiceSerializer, AuditLogSerializer, AppSettingsSerializer,
    NotificationTemplateSerializer, DashboardStatsSerializer, DealerStatsSerializer,
    ProductStatsSerializer, UserSerializer, DealerContextSerializer
)


class DepotViewSet(viewsets.ModelViewSet):
    queryset = Depot.objects.all().order_by('name')
    serializer_class = DepotSerializer
    search_fields = ['name', 'code', 'city', 'state']
    ordering_fields = ['name', 'code', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_depots = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(active_depots, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('name')
    serializer_class = ProductSerializer
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_products = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(active_products, many=True)
        return Response(serializer.data)


class DealerViewSet(viewsets.ModelViewSet):
    queryset = Dealer.objects.all().order_by('name')
    serializer_class = DealerSerializer
    search_fields = ['name', 'code', 'contact_person', 'phone', 'email', 'city']
    ordering_fields = ['name', 'code', 'created_at', 'credit_limit']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_dealers = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(active_dealers, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        dealer = self.get_object()
        orders = Order.objects.filter(dealer=dealer).order_by('-order_date')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        dealer = self.get_object()
        now = timezone.now()
        orders = Order.objects.filter(dealer=dealer)
        
        stats = {
            'total_orders': orders.count(),
            'weekly_orders': orders.filter(order_date__gte=now-timedelta(days=7)).count(),
            'monthly_orders': orders.filter(order_date__gte=now-timedelta(days=30)).count(),
            'pending_orders': orders.filter(status__in=['PENDING', 'CONFIRMED']).count(),
            'completed_orders': orders.filter(status='DELIVERED').count(),
            'total_value': orders.aggregate(
                total=Sum('order_items__quantity') * Sum('order_items__unit_price')
            )['total'] or 0,
        }
        return Response(stats)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all().order_by('truck_number')
    serializer_class = VehicleSerializer
    search_fields = ['truck_number', 'owner_name', 'driver_name', 'driver_phone']
    ordering_fields = ['truck_number', 'capacity', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        active_vehicles = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(active_vehicles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        vehicle = self.get_object()
        orders = Order.objects.filter(vehicle=vehicle).order_by('-order_date')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-order_date')
    search_fields = ['order_number', 'dealer__name', 'vehicle__truck_number', 'status']
    ordering_fields = ['order_date', 'order_number', 'status']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        status_param = request.query_params.get('status', 'PENDING')
        orders = self.queryset.filter(status=status_param)
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending_orders = self.queryset.filter(status__in=['PENDING', 'CONFIRMED'])
        serializer = self.get_serializer(pending_orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        today_orders = self.queryset.filter(order_date__date=date.today())
        serializer = self.get_serializer(today_orders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        
        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            
            # Update related dates based on status
            if new_status == 'MRN_CREATED' and not order.mrn_date:
                order.mrn_date = date.today()
            elif new_status == 'BILLED' and not order.bill_date:
                order.bill_date = date.today()
            elif new_status == 'DISPATCHED' and not order.dispatch_date:
                order.dispatch_date = timezone.now()
            elif new_status == 'DELIVERED' and not order.delivery_date:
                order.delivery_date = timezone.now()
            
            order.save()
            
            # Create audit log
            AuditLog.objects.create(
                action='ORDER_UPDATED',
                model_name='Order',
                object_id=str(order.id),
                user=request.user,
                details={
                    'old_status': old_status,
                    'new_status': new_status,
                    'order_number': order.order_number
                }
            )
            
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        
        return Response(
            {'error': 'Invalid status'}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    
    def get_queryset(self):
        order_id = self.request.query_params.get('order_id')
        if order_id:
            return self.queryset.filter(order_id=order_id)
        return self.queryset


class MRNViewSet(viewsets.ModelViewSet):
    queryset = MRN.objects.all().order_by('-mrn_date')
    serializer_class = MRNSerializer
    search_fields = ['mrn_number', 'order__order_number', 'status']
    ordering_fields = ['mrn_date', 'mrn_number', 'status']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        mrn = self.get_object()
        mrn.status = 'APPROVED'
        mrn.approved_by = request.user
        mrn.save()
        
        # Update order status
        mrn.order.status = 'MRN_CREATED'
        mrn.order.mrn_date = mrn.mrn_date
        mrn.order.save()
        
        # Create audit log
        AuditLog.objects.create(
            action='MRN_APPROVED',
            model_name='MRN',
            object_id=str(mrn.id),
            user=request.user,
            details={
                'mrn_number': mrn.mrn_number,
                'order_number': mrn.order.order_number
            }
        )
        
        serializer = self.get_serializer(mrn)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending_mrns = self.queryset.filter(status='PENDING')
        serializer = self.get_serializer(pending_mrns, many=True)
        return Response(serializer.data)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-invoice_date')
    serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'order__order_number', 'status']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        today = date.today()
        overdue_invoices = self.queryset.filter(
            due_date__lt=today,
            status__in=['DRAFT', 'SENT']
        )
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        invoice = self.get_object()
        payment_amount = request.data.get('payment_amount', invoice.total_amount)
        payment_date = request.data.get('payment_date', date.today())
        
        invoice.payment_received = payment_amount
        invoice.payment_date = payment_date
        invoice.status = 'PAID' if payment_amount >= invoice.total_amount else 'SENT'
        invoice.save()
        
        # Create audit log
        AuditLog.objects.create(
            action='PAYMENT_RECEIVED',
            model_name='Invoice',
            object_id=str(invoice.id),
            user=request.user,
            details={
                'invoice_number': invoice.invoice_number,
                'payment_amount': str(payment_amount),
                'payment_date': str(payment_date)
            }
        )
        
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by('-created_at')
    serializer_class = AuditLogSerializer
    search_fields = ['action', 'model_name', 'object_id', 'user__username']
    ordering_fields = ['created_at', 'action']


class AppSettingsViewSet(viewsets.ModelViewSet):
    queryset = AppSettings.objects.all().order_by('key')
    serializer_class = AppSettingsSerializer
    search_fields = ['key', 'description']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all().order_by('name')
    serializer_class = NotificationTemplateSerializer
    search_fields = ['name', 'type']
    ordering_fields = ['name', 'type', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        template_type = request.query_params.get('type', 'WHATSAPP')
        templates = self.queryset.filter(type=template_type, is_active=True)
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)
    
class DealerContextViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DealerContext with read and create operations only.
    Update and delete operations are disabled for audit trail integrity.
    """
    queryset = DealerContext.objects.all().order_by('-interaction_date')
    serializer_class = DealerContextSerializer
    search_fields = [
        'dealer__name', 'dealer__code', 'interaction_summary', 
        'detailed_notes', 'tags', 'topics_discussed'
    ]
    filterset_fields = [
        'dealer', 'interaction_type', 'sentiment', 'priority_level',
        'follow_up_required', 'issue_resolved'
    ]
    ordering_fields = ['interaction_date', 'dealer__name', 'priority_level', 'sentiment']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def update(self, request, *args, **kwargs):
        """Disable update operations"""
        return Response(
            {'detail': 'Update operations are not allowed for dealer contexts.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Disable partial update operations"""
        return Response(
            {'detail': 'Update operations are not allowed for dealer contexts.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Disable delete operations"""
        return Response(
            {'detail': 'Delete operations are not allowed for dealer contexts.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    @action(detail=False, methods=['get'])
    def by_dealer(self, request):
        """Get all contexts for a specific dealer"""
        dealer_id = request.query_params.get('dealer_id')
        if not dealer_id:
            return Response(
                {'detail': 'dealer_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contexts = self.queryset.filter(dealer_id=dealer_id)
        page = self.paginate_queryset(contexts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(contexts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def follow_ups_due(self, request):
        """Get contexts with overdue follow-ups"""
        now = timezone.now()
        overdue_contexts = self.queryset.filter(
            follow_up_required=True,
            follow_up_date__lt=now,
            issue_resolved=False
        )
        
        serializer = self.get_serializer(overdue_contexts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def high_priority(self, request):
        """Get high priority contexts"""
        high_priority_contexts = self.queryset.filter(
            priority_level__in=['HIGH', 'CRITICAL']
        )
        
        serializer = self.get_serializer(high_priority_contexts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent_interactions(self, request):
        """Get recent interactions within last 7 days"""
        week_ago = timezone.now() - timedelta(days=7)
        recent_contexts = self.queryset.filter(interaction_date__gte=week_ago)
        
        serializer = self.get_serializer(recent_contexts, many=True)
        return Response(serializer.data)


# Dashboard and Analytics APIs
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    today = date.today()
    
    stats = {
        'orders_created_today': Order.objects.filter(order_date__date=today).count(),
        'mrn_approved_today': MRN.objects.filter(mrn_date=today, status='APPROVED').count(),
        'orders_billed_today': Order.objects.filter(bill_date=today).count(),
        'total_orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status__in=['PENDING', 'CONFIRMED']).count(),
        'completed_orders': Order.objects.filter(status='DELIVERED').count(),
        'active_dealers': Dealer.objects.filter(is_active=True).count(),
        'active_vehicles': Vehicle.objects.filter(is_active=True).count(),
    }
    
    serializer = DashboardStatsSerializer(stats)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dealer_analytics(request):
    dealers = Dealer.objects.filter(is_active=True)
    dealer_stats = []
    
    for dealer in dealers:
        orders = Order.objects.filter(dealer=dealer)
        now = timezone.now()
        
        stats = {
            'dealer_id': dealer.id,
            'dealer_name': dealer.name,
            'weekly_orders': orders.filter(order_date__gte=now-timedelta(days=7)).count(),
            'monthly_orders': orders.filter(order_date__gte=now-timedelta(days=30)).count(),
            'total_orders': orders.count(),
            'avg_order_value': orders.aggregate(
                avg=Avg('order_items__quantity')
            )['avg'] or 0,
        }
        dealer_stats.append(stats)
    
    # Sort by monthly orders descending
    dealer_stats.sort(key=lambda x: x['monthly_orders'], reverse=True)
    
    serializer = DealerStatsSerializer(dealer_stats, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_analytics(request):
    products = Product.objects.filter(is_active=True)
    product_stats = []
    
    for product in products:
        order_items = OrderItem.objects.filter(product=product)
        
        stats = {
            'product_name': product.name,
            'total_orders': order_items.values('order').distinct().count(),
            'total_quantity': order_items.aggregate(total=Sum('quantity'))['total'] or 0,
            'avg_quantity_per_order': order_items.aggregate(avg=Avg('quantity'))['avg'] or 0,
        }
        product_stats.append(stats)
    
    # Sort by total quantity descending
    product_stats.sort(key=lambda x: x['total_quantity'], reverse=True)
    
    serializer = ProductStatsSerializer(product_stats, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_analytics(request):
    # Date range filter
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    orders = Order.objects.all()
    
    if start_date:
        orders = orders.filter(order_date__date__gte=start_date)
    if end_date:
        orders = orders.filter(order_date__date__lte=end_date)
    
    # Status distribution
    status_counts = orders.values('status').annotate(count=Count('id'))
    
    # Monthly trends (last 12 months)
    monthly_stats = []
    for i in range(12):
        month_start = date.today().replace(day=1) - timedelta(days=i*30)
        month_orders = orders.filter(
            order_date__year=month_start.year,
            order_date__month=month_start.month
        )
        
        monthly_stats.append({
            'month': month_start.strftime('%B %Y'),
            'order_count': month_orders.count(),
            'total_quantity': month_orders.aggregate(
                total=Sum('order_items__quantity')
            )['total'] or 0,
        })
    
    # Depot-wise distribution
    depot_stats = orders.values('depot__name').annotate(
        order_count=Count('id'),
        total_quantity=Sum('order_items__quantity')
    ).order_by('-order_count')
    
    return Response({
        'status_distribution': list(status_counts),
        'monthly_trends': monthly_stats[::-1],  # Reverse to show oldest first
        'depot_distribution': list(depot_stats),
        'total_orders': orders.count(),
        'avg_order_value': orders.aggregate(
            avg=Avg('order_items__quantity')
        )['avg'] or 0,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)



