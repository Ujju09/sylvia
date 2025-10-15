from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from sylvia.storage import krutrim_storage
from sylvia.serializers import LoadingRequestImageSerializer
from .models import LoadingRequestImage
import requests


class LoadingRequestImageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Loading Request proof images"""
    queryset = LoadingRequestImage.objects.all().order_by('-upload_timestamp')
    serializer_class = LoadingRequestImageSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['loading_request__loading_request_id', 'original_filename', 'image_type']
    ordering_fields = ['upload_timestamp', 'image_type', 'is_primary']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Delete image from both database and storage"""
        image_record = self.get_object()

        # Delete from storage first
        if image_record.storage_key:
            success, message = krutrim_storage.delete_image(image_record.storage_key)
            if not success:
                return Response(
                    {'error': f'Failed to delete from storage: {message}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Delete from database
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def by_loading_request(self, request):
        """Get all images for a specific loading request"""
        loading_request_id = request.query_params.get('loading_request_id')
        if not loading_request_id:
            return Response(
                {'error': 'loading_request_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        images = self.queryset.filter(loading_request__loading_request_id=loading_request_id)
        serializer = self.get_serializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set image as primary loading proof for the loading request"""
        image_record = self.get_object()

        # Unset all other primary images for this loading request
        LoadingRequestImage.objects.filter(
            loading_request=image_record.loading_request,
            is_primary=True
        ).update(is_primary=False)

        # Set this image as primary
        image_record.is_primary = True
        image_record.save()

        serializer = self.get_serializer(image_record, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Filter images by type"""
        image_type = request.query_params.get('type', 'LOADING_PROOF')
        images = self.queryset.filter(image_type=image_type)
        serializer = self.get_serializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def serve_image(self, request, pk=None):
        """Serve image with proper authentication - fallback proxy"""
        try:
            image_record = self.get_object()

            if not image_record.storage_key:
                return Response(
                    {'error': 'Image storage key not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Construct the image URL
            image_url = f"{krutrim_storage.endpoint_url}/{krutrim_storage.bucket_name}/{image_record.storage_key}"

            # Create authenticated headers using AWS Signature Version 4
            headers = krutrim_storage._create_auth_headers_v4(
                method='GET',
                url=image_url,
                content_type=''
            )

            # Fetch the image from Krutrim Storage
            response = requests.get(image_url, headers=headers, timeout=30)

            if response.status_code == 200:
                # Determine content type
                content_type = image_record.content_type or 'image/jpeg'

                # Create HTTP response with image data
                http_response = HttpResponse(
                    response.content,
                    content_type=content_type
                )
                http_response['Content-Disposition'] = f'inline; filename="{image_record.original_filename}"'
                http_response['Cache-Control'] = 'private, max-age=3600'  # Cache for 1 hour

                return http_response
            else:
                return Response(
                    {'error': f'Failed to fetch image: HTTP {response.status_code}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            return Response(
                {'error': f'Error serving image: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
