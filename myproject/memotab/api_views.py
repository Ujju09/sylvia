from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions, BasePermission
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth.models import User

from .models import Source, CashCollect
from .serializers import (
    SourceSerializer, CashCollectSerializer, CashCollectListSerializer,
    CashCollectCreateSerializer, UserSerializer
)

try:
    from .schemas import (
        CashCollectCreate, CashCollectUpdate, CashCollectResponse,
        SourceCreate, SourceUpdate, SourceResponse,
        ErrorResponse, SuccessResponse
    )
    PYDANTIC_AVAILABLE = True
except (ImportError, Exception):
    PYDANTIC_AVAILABLE = False


class IsMemoTabUser(BasePermission):
    """
    Custom permission to ensure only authenticated users can access MemoTab data.
    Staff users can access all data, regular users can only access data they're involved with.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Staff users have full access
        if request.user.is_staff:
            return True
        
        # For CashCollect objects, users can access if they created it or received it
        if hasattr(obj, 'received_by') and hasattr(obj, 'created_by'):
            return (obj.received_by == request.user or 
                    obj.created_by == request.user)
        
        # For Source objects, users can access if they created it
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        # Default: allow access
        return True


class SourceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing cash collection sources"""
    queryset = Source.objects.all().order_by('text')
    serializer_class = SourceSerializer
    permission_classes = [IsAuthenticated, IsMemoTabUser]
    search_fields = ['text']
    ordering_fields = ['text', 'created_at', 'updated_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            # Non-staff users can only see sources they created
            queryset = queryset.filter(created_by=self.request.user)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a new source with Pydantic validation if available"""
        if PYDANTIC_AVAILABLE:
            try:
                # Validate with Pydantic
                pydantic_data = SourceCreate(**request.data)
                validated_data = pydantic_data.dict()
            except Exception as e:
                return Response(
                    {"error": "Validation failed", "detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            validated_data = request.data
        
        # Create using DRF serializer
        serializer = self.get_serializer(data=validated_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active sources"""
        active_sources = self.queryset.filter(is_active=True)
        serializer = self.get_serializer(active_sources, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle the active status of a source"""
        source = self.get_object()
        source.is_active = not source.is_active
        source.save()
        
        serializer = self.get_serializer(source)
        return Response({
            'message': f'Source {"activated" if source.is_active else "deactivated"} successfully',
            'data': serializer.data
        })


class CashCollectViewSet(viewsets.ModelViewSet):
    """ViewSet for managing cash collection records"""
    queryset = CashCollect.objects.select_related('source', 'received_by', 'created_by').order_by('-date', '-created_at')
    permission_classes = [IsAuthenticated, IsMemoTabUser]
    search_fields = ['note', 'source__text', 'received_by__username']
    ordering_fields = ['date', 'amount', 'created_at', 'updated_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            # Non-staff users can only see cash collections they created or received
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(received_by=self.request.user)
            )
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return CashCollectListSerializer
        elif self.action == 'create':
            return CashCollectCreateSerializer
        return CashCollectSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create a new cash collection with Pydantic validation if available"""
        if PYDANTIC_AVAILABLE:
            try:
                # Validate with Pydantic
                pydantic_data = CashCollectCreate(**request.data)
                validated_data = pydantic_data.dict()
            except Exception as e:
                return Response(
                    {"error": "Validation failed", "detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            validated_data = request.data
        
        # Create using DRF serializer
        serializer = self.get_serializer(data=validated_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Update cash collection with Pydantic validation if available"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if PYDANTIC_AVAILABLE:
            try:
                # Validate with Pydantic
                pydantic_data = CashCollectUpdate(**request.data)
                validated_data = pydantic_data.dict(exclude_unset=True)
            except Exception as e:
                return Response(
                    {"error": "Validation failed", "detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            validated_data = request.data
        
        serializer = self.get_serializer(instance, data=validated_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's cash collections"""
        today = timezone.now().date()
        today_collections = self.queryset.filter(date=today)
        
        page = self.paginate_queryset(today_collections)
        if page is not None:
            serializer = CashCollectListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CashCollectListSerializer(today_collections, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_date_range(self, request):
        """Get cash collections within a date range"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {"error": "Both start_date and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        collections = self.queryset.filter(date__gte=start_date, date__lte=end_date)
        
        page = self.paginate_queryset(collections)
        if page is not None:
            serializer = CashCollectListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CashCollectListSerializer(collections, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_source(self, request):
        """Get cash collections by source"""
        source_id = request.query_params.get('source_id')
        
        if not source_id:
            return Response(
                {"error": "source_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            source_id = int(source_id)
        except ValueError:
            return Response(
                {"error": "Invalid source_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        collections = self.queryset.filter(source_id=source_id)
        
        page = self.paginate_queryset(collections)
        if page is not None:
            serializer = CashCollectListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CashCollectListSerializer(collections, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get cash collection statistics"""
        # Get query parameters for date filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.queryset
        
        if start_date and end_date:
            try:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=start_date, date__lte=end_date)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Calculate statistics
        stats = queryset.aggregate(
            total_amount=Sum('amount'),
            total_collections=Count('id'),
            avg_amount=Sum('amount')
        )
        
        # Get stats by source
        source_stats = (
            queryset.values('source__text', 'source__id')
            .annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            .order_by('-total_amount')
        )
        
        # Get stats by receiver
        receiver_stats = (
            queryset.values('received_by__username', 'received_by__id')
            .annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            .order_by('-total_amount')
        )
        
        return Response({
            'overall_stats': stats,
            'by_source': list(source_stats),
            'by_receiver': list(receiver_stats),
            'date_range': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
            }
        })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for user information (read-only for cash collection purposes)"""
    queryset = User.objects.filter(is_active=True).order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering_fields = ['username', 'first_name', 'last_name']