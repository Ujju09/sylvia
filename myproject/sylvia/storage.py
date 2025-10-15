import os
import uuid
import mimetypes
import requests
import hashlib
import hmac
import datetime
from django.conf import settings
from typing import Dict, Optional, Tuple, Union
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
import logging
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)

class KrutrimStorageClient:
    """Client for Krutrim Storage API (S3-compatible)"""
    
    def __init__(self):
        self.access_key = getattr(settings, 'KRUTRIM_STORAGE_ACCESS_KEY', '')
        self.secret_key = getattr(settings, 'KRUTRIM_STORAGE_API_KEY', '')  # API key is used as secret key
        self.bucket_name = getattr(settings, 'KRUTRIM_STORAGE_BUCKET', 'mrn-receipts-datastore')
        self.endpoint_url = getattr(settings, 'KRUTRIM_STORAGE_ENDPOINT', '')
        self.region = getattr(settings, 'KRUTRIM_STORAGE_REGION', 'in-bangalore-1')
        
        if not self.access_key or not self.secret_key or not self.endpoint_url:
            raise ValueError("Krutrim Storage credentials not properly configured. Please set KRUTRIM_STORAGE_ACCESS_KEY, KRUTRIM_STORAGE_API_KEY and KRUTRIM_STORAGE_ENDPOINT in your environment variables.")
        
    
    def _create_auth_headers_v4(self, method: str, url: str, content_type: str = 'application/octet-stream', payload_hash: str = None) -> dict:
        """Create AWS Signature Version 4 authorization headers for Krutrim Storage"""
        
        # Parse URL components
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        canonical_uri = parsed_url.path
        canonical_querystring = parsed_url.query or ''
        
        # Create timestamp
        t = datetime.datetime.now()
        amzdate = t.strftime('%Y%m%dT%H%M%SZ')
        datestamp = t.strftime('%Y%m%d')
        
        # Calculate payload hash
        if payload_hash is None:
            payload_hash = hashlib.sha256(b'').hexdigest()
        
        # Create canonical headers
        canonical_headers = f'host:{host}\n'
        canonical_headers += f'x-amz-content-sha256:{payload_hash}\n'
        canonical_headers += f'x-amz-date:{amzdate}\n'
        
        # Create signed headers
        signed_headers = 'host;x-amz-content-sha256;x-amz-date'
        
        # Create canonical request
        canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
        
        # Create string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f'{datestamp}/{self.region}/s3/aws4_request'
        string_to_sign = f'{algorithm}\n{amzdate}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}'
        
        # Create signing key
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        def getSignatureKey(key, datestamp, regionName, serviceName):
            kDate = sign(('AWS4' + key).encode('utf-8'), datestamp)
            kRegion = sign(kDate, regionName)
            kService = sign(kRegion, serviceName)
            kSigning = sign(kService, 'aws4_request')
            return kSigning
        
        signing_key = getSignatureKey(self.secret_key, datestamp, self.region, 's3')
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Create authorization header
        authorization_header = f'{algorithm} Credential={self.access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
        
        headers = {
            'Authorization': authorization_header,
            'x-amz-content-sha256': payload_hash,
            'x-amz-date': amzdate,
            'Content-Type': content_type,
        }
        
        return headers
    
    
    def _validate_image_file(self, file_obj: Union[InMemoryUploadedFile, TemporaryUploadedFile]) -> Tuple[bool, str]:
        """Validate uploaded image file"""
        try:
            # Check file size (10MB limit)
            max_size = 10 * 1024 * 1024  # 5MB
            if file_obj.size > max_size:
                return False, f"File size too large. Maximum allowed: 10MB, got: {file_obj.size / (1024*1024):.1f}MB"
            
            # Check content type
            allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
            content_type = file_obj.content_type or mimetypes.guess_type(file_obj.name)[0]
            
            if content_type not in allowed_types:
                return False, f"Invalid file type. Allowed: {', '.join(allowed_types)}, got: {content_type}"
            
            # Check file extension
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            file_ext = os.path.splitext(file_obj.name.lower())[1]
            
            if file_ext not in allowed_extensions:
                return False, f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}, got: {file_ext}"
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return False, f"Error validating file: {str(e)}"
    
    def _generate_storage_key(self, order_number: str, filename: str) -> str:
        """Generate unique storage key for the file"""
        # Create a unique identifier
        unique_id = str(uuid.uuid4())[:8]

        # Create hierarchical key: orders/{order_number}/mrn_images/{unique_id}_{filename}
        storage_key = f"sylvia/orders/{order_number}/mrn_images/{unique_id}_{filename}"
        return storage_key

    def _generate_loading_storage_key(self, loading_request_id: str, filename: str) -> str:
        """Generate unique storage key for loading request images"""
        # Create a unique identifier
        unique_id = str(uuid.uuid4())[:8]

        # Create hierarchical key: godown/loading_requests/{loading_request_id}/images/{unique_id}_{filename}
        storage_key = f"godown/loading_requests/{loading_request_id}/images/{unique_id}_{filename}"
        return storage_key
    
    def upload_image(self, file_obj: Union[InMemoryUploadedFile, TemporaryUploadedFile], 
                    order_number: str) -> Tuple[bool, str, Optional[str], Optional[Dict]]:
        """
        Upload image to Krutrim Storage using custom HTTP client
        Returns: (success, url_or_error_message, storage_key, metadata)
        """
        try:
            # Validate file
            is_valid, validation_message = self._validate_image_file(file_obj)
            if not is_valid:
                return False, validation_message, None, None
            
            # Generate storage key
            storage_key = self._generate_storage_key(order_number, file_obj.name)
            
            # Reset file pointer
            file_obj.seek(0)
            
            # Construct upload URL
            upload_url = f"{self.endpoint_url}/{self.bucket_name}/{quote(storage_key, safe='/')}"
            
            # Get content type
            content_type = file_obj.content_type or mimetypes.guess_type(file_obj.name)[0] or 'application/octet-stream'
            
            # Read file content to calculate SHA256 hash (required for SigV4)
            file_content = file_obj.read()
            payload_hash = hashlib.sha256(file_content).hexdigest()
            
            # Create headers with AWS Signature Version 4
            headers = self._create_auth_headers_v4(
                method='PUT', 
                url=upload_url, 
                content_type=content_type,
                payload_hash=payload_hash
            )
            
            # Upload file using HTTP PUT request
            try:
                response = requests.put(
                    upload_url,
                    data=file_content,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code in [200, 201]:
                    # Construct the public URL
                    image_url = upload_url
                    
                    metadata = {
                        'original_filename': file_obj.name,
                        'file_size': file_obj.size,
                        'content_type': content_type,
                        'storage_key': storage_key
                    }
                    
                    return True, image_url, storage_key, metadata
                else:
                    error_msg = f"Krutrim Storage upload failed: HTTP {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, error_msg, None, None
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Error during HTTP upload: {str(e)}"
                logger.error(error_msg)
                return False, error_msg, None, None
            
        except Exception as e:
            error_msg = f"Error uploading image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None, None

    def upload_loading_image(self, file_obj: Union[InMemoryUploadedFile, TemporaryUploadedFile],
                            loading_request_id: str) -> Tuple[bool, str, Optional[str], Optional[Dict]]:
        """
        Upload loading request image to Krutrim Storage using custom HTTP client
        Returns: (success, url_or_error_message, storage_key, metadata)
        """
        try:
            # Validate file
            is_valid, validation_message = self._validate_image_file(file_obj)
            if not is_valid:
                return False, validation_message, None, None

            # Generate storage key for loading requests
            storage_key = self._generate_loading_storage_key(loading_request_id, file_obj.name)

            # Reset file pointer
            file_obj.seek(0)

            # Construct upload URL
            upload_url = f"{self.endpoint_url}/{self.bucket_name}/{quote(storage_key, safe='/')}"

            # Get content type
            content_type = file_obj.content_type or mimetypes.guess_type(file_obj.name)[0] or 'application/octet-stream'

            # Read file content to calculate SHA256 hash (required for SigV4)
            file_content = file_obj.read()
            payload_hash = hashlib.sha256(file_content).hexdigest()

            # Create headers with AWS Signature Version 4
            headers = self._create_auth_headers_v4(
                method='PUT',
                url=upload_url,
                content_type=content_type,
                payload_hash=payload_hash
            )

            # Upload file using HTTP PUT request
            try:
                response = requests.put(
                    upload_url,
                    data=file_content,
                    headers=headers,
                    timeout=60
                )

                if response.status_code in [200, 201]:
                    # Construct the public URL
                    image_url = upload_url

                    metadata = {
                        'original_filename': file_obj.name,
                        'file_size': file_obj.size,
                        'content_type': content_type,
                        'storage_key': storage_key
                    }

                    return True, image_url, storage_key, metadata
                else:
                    error_msg = f"Krutrim Storage upload failed: HTTP {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, error_msg, None, None

            except requests.exceptions.RequestException as e:
                error_msg = f"Error during HTTP upload: {str(e)}"
                logger.error(error_msg)
                return False, error_msg, None, None

        except Exception as e:
            error_msg = f"Error uploading loading image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None, None

    def delete_image(self, storage_key: str) -> Tuple[bool, str]:
        """Delete image from Krutrim Storage using custom HTTP client"""
        try:
            # Construct delete URL
            delete_url = f"{self.endpoint_url}/{self.bucket_name}/{quote(storage_key, safe='/')}"
            
            # Create headers with AWS Signature Version 4
            headers = self._create_auth_headers_v4(method='DELETE', url=delete_url, content_type='')
            
            try:
                response = requests.delete(
                    delete_url,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code in [200, 204]:
                    return True, "Image deleted successfully"
                else:
                    error_msg = f"Krutrim Storage delete failed: HTTP {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, error_msg
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Error during HTTP delete: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Error deleting image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def generate_presigned_url(self, storage_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for secure access using AWS Signature Version 4"""
        try:
            # Calculate expiration timestamp
            t = datetime.datetime.utcnow()
            amzdate = t.strftime('%Y%m%dT%H%M%SZ')
            datestamp = t.strftime('%Y%m%d')
            
            # Parse URL components
            object_url = f"{self.endpoint_url}/{self.bucket_name}/{quote(storage_key, safe='/')}"
            parsed_url = urlparse(object_url)
            host = parsed_url.netloc
            canonical_uri = parsed_url.path
            
            # Create credential scope
            credential_scope = f'{datestamp}/{self.region}/s3/aws4_request'
            credential = f'{self.access_key}/{credential_scope}'
            
            # Create query parameters for presigned URL
            query_params = {
                'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
                'X-Amz-Credential': credential,
                'X-Amz-Date': amzdate,
                'X-Amz-Expires': str(expiration),
                'X-Amz-SignedHeaders': 'host'
            }
            
            # Sort query parameters
            sorted_params = sorted(query_params.items())
            canonical_querystring = '&'.join([f'{k}={quote(str(v), safe="-_.~")}' for k, v in sorted_params])
            
            # Create canonical headers
            canonical_headers = f'host:{host}\n'
            
            # Create canonical request for presigned URL
            payload_hash = 'UNSIGNED-PAYLOAD'
            canonical_request = f'GET\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\nhost\n{payload_hash}'
            
            # Create string to sign
            algorithm = 'AWS4-HMAC-SHA256'
            string_to_sign = f'{algorithm}\n{amzdate}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}'
            
            # Create signing key
            def sign(key, msg):
                return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
            
            def getSignatureKey(key, datestamp, regionName, serviceName):
                kDate = sign(('AWS4' + key).encode('utf-8'), datestamp)
                kRegion = sign(kDate, regionName)
                kService = sign(kRegion, serviceName)
                kSigning = sign(kService, 'aws4_request')
                return kSigning
            
            signing_key = getSignatureKey(self.secret_key, datestamp, self.region, 's3')
            signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            
            # Add signature to query parameters
            query_params['X-Amz-Signature'] = signature
            
            # Build final presigned URL
            final_params = '&'.join([f'{k}={quote(str(v), safe="-_.~")}' for k, v in sorted(query_params.items())])
            presigned_url = f"{object_url}?{final_params}"
            
            return presigned_url
            
        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None
    
    def get_file_info(self, storage_key: str) -> Optional[Dict]:
        """Get file metadata from storage using custom HTTP client"""
        try:
            # Construct HEAD request URL
            head_url = f"{self.endpoint_url}/{self.bucket_name}/{quote(storage_key, safe='/')}"
            
            # Create headers with AWS Signature Version 4
            headers = self._create_auth_headers_v4(method='HEAD', url=head_url, content_type='')
            
            try:
                response = requests.head(
                    head_url,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return {
                        'storage_key': storage_key,
                        'size': int(response.headers.get('Content-Length', 0)),
                        'content_type': response.headers.get('Content-Type', 'application/octet-stream'),
                        'last_modified': response.headers.get('Last-Modified', ''),
                        'etag': response.headers.get('ETag', '').strip('"'),
                    }
                elif response.status_code == 404:
                    logger.warning(f"File not found: {storage_key}")
                    return None
                else:
                    logger.error(f"Krutrim Storage HEAD failed: HTTP {response.status_code} - {response.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error during HTTP HEAD request: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return None


# Singleton instance
krutrim_storage = KrutrimStorageClient()