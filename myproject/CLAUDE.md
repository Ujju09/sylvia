# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based Order Management System for a cement distribution company (Shyam Distributors - CFA Garhwa and Palamu). The system manages orders, vehicles, dealers, products, depots, MRNs (Material Receipt Notes), and invoicing workflow.

## Development Commands

### Local Development
```bash
# Install dependencies
pip3 install -r requirements.txt

# Database migrations
python3 manage.py makemigrations
python3 manage.py migrate

# Create superuser (for admin access)
python3 manage.py createsuperuser

# Run development server
python3 manage.py runserver

# Collect static files (for production)
python3 manage.py collectstatic

# Load initial data
python3 manage.py loaddata sylvia/fixtures/dummy_data.json
```

### Production Deployment
The application is configured for Railway deployment with PostgreSQL database:
```bash
# Production start command (defined in railway.toml)
python3 manage.py migrate && python3 manage.py createsuperuser --noinput && python3 manage.py collectstatic --noinput && gunicorn myproject.wsgi
```

## Core Architecture

### Django Apps Structure
- **myproject/**: Main Django project configuration
- **sylvia/**: Core business logic app containing models, API views, serializers
- **orders/**: Web interface app for order management and workflow views
- **memotab/**: Standalone API-only app for cash collection management with Pydantic integration

### Key Models (sylvia/models.py)
- **BaseModel**: Abstract base with created_at, updated_at, created_by fields
- **Depot**: Warehouse/depot locations
- **Product**: Materials/products (cement types)
- **Dealer**: Customers/dealers
- **Vehicle**: Trucks for transportation
- **Order**: Main order entity with auto-generated order numbers
- **OrderItem**: Line items for orders (product + quantity)
- **MRN**: Material Receipt Notes for quality approval
- **OrderMRNImage**: MRN proof images with cloud storage integration
- **Invoice**: Billing/invoice management
- **AuditLog**: Audit trail for important actions
- **DealerContext**: AI-enhanced relationship management with psychological assessment

### MemoTab Models (memotab/models.py)
- **Source**: Cash collection sources with text description and active status
- **CashCollect**: Cash collection records with date, source, amount, received_by, and note fields
- **BaseModel**: Shared abstract base model pattern (consistent with sylvia app)

### API Architecture
#### Main API (sylvia/)
- RESTful API using Django REST Framework
- Token-based authentication
- ViewSets for CRUD operations
- Custom actions for business workflows
- Comprehensive analytics endpoints

#### MemoTab API (memotab/)
- Standalone API-only app accessible via `/api/v1/memotab/`
- Pydantic integration for strong typing with automatic fallback
- Custom permission class `IsMemoTabUser` for enhanced security:
  - Staff users have full access to all data
  - Regular users can only access data they created or are involved with
- Filtered querysets ensure data isolation for non-staff users

### Web Interface (orders/)
- Django template-based views
- Order workflow management
- Analytics dashboard
- Complete vehicle management (list, add, edit, delete)
- Complete dealer management (list, add, edit, delete)
- Product and depot management (add forms)
- Export functionality (Excel/PDF)
- Enhanced order list with visual indicators for remarks and MRN images
- Comprehensive order detail view with remarks display and image gallery

## Business Workflow

1. **Order Creation**: Create orders with dealer, vehicle, depot, and products
2. **AI-Powered Dispatch Processing**: Upload dispatch table images for automated order extraction
3. **MRN Process**: Quality check and approval workflow with image proof upload
4. **MRN Image Management**: Upload, view, and manage MRN proof images with cloud storage
5. **Billing**: Invoice generation and payment tracking
6. **Analytics**: Performance tracking and reporting with enhanced filtering
7. **Proactive Dealer Management**: Daily recommendations for dealer outreach with complete order history

## UI Enhancements

### Order Management Interface

#### Enhanced Order List View
The order list interface provides comprehensive visibility and navigation aids:

- **Visual Indicators Column**: Displays at-a-glance information for each order
  - **Remarks Badge**: Yellow warning badge with comment icon when order has remarks
  - **Images Badge**: Blue info badge with image icon and count showing number of MRN images
- **Interactive Tooltips**: Hover over indicators to see preview information
  - Remarks tooltip shows truncated remarks content (up to 100 characters)
  - Images tooltip shows exact count with proper pluralization
- **Quick Navigation**: Visual cues help prioritize which orders need attention
- **Responsive Design**: Indicators adapt to different screen sizes

#### Comprehensive Order Detail View
The order detail page provides complete order information with enhanced visibility:

- **Remarks Display**: Dedicated remarks section with visual styling
  - Only shows when remarks exist to avoid clutter
  - Uses card layout with proper typography for easy reading
  - Preserves line breaks for multi-line remarks using `|linebreaks` filter
  - Positioned in the order status area for logical grouping
- **MRN Image Gallery**: Visual gallery of all uploaded proof images
  - Thumbnail grid with modal preview functionality
  - Image metadata display (filename, type, upload date, file size)
  - Primary image indicators and user attribution
  - Secure image serving with presigned URLs

#### Navigation Benefits
- **Informed Decision Making**: Quickly identify orders with additional documentation
- **Efficient Workflow**: Prioritize orders needing attention based on visual cues
- **Complete Context**: Access all order information including remarks and images in one view
- **User-Friendly**: Intuitive icons and tooltips provide guidance without training

## MRN Image Upload System

### Overview
The MRN Image Upload System provides secure cloud storage and management of Material Receipt Note proof images using Krutrim Storage (S3-compatible cloud service).

### Key Features
- **Drag-and-Drop Upload**: Modern web interface with drag-and-drop functionality
- **Cloud Storage Integration**: Secure storage using Krutrim Storage with AWS Signature Version 4 authentication
- **Presigned URLs**: Time-limited secure access URLs for viewing images without exposing credentials
- **Image Management**: Full CRUD operations (Create, Read, Update, Delete) for image records
- **Multiple Image Types**: Support for MRN Proof, Delivery Receipt, Quality Check, and Other image types
- **Primary Image Selection**: Mark images as primary proof for quick identification
- **Comprehensive Validation**: File type, size, and format validation (JPG, PNG, WEBP, max 10MB)
- **Audit Trail**: Complete tracking of image uploads, modifications, and deletions

### Technical Architecture

#### Storage Layer (sylvia/storage.py)
- **KrutrimStorageClient**: Custom S3-compatible client with AWS Signature Version 4 authentication
- **Presigned URL Generation**: Secure, time-limited URLs (1-hour expiration) for image access
- **File Validation**: Content type, file size, and extension validation
- **Hierarchical Storage**: Organized storage structure: `sylvia/orders/{order_number}/mrn_images/{unique_id}_{filename}`

#### API Layer (sylvia/api_views.py)
- **OrderMRNImageViewSet**: Complete REST API for image management
- **Upload Endpoints**: Secure image upload with authentication and validation
- **Proxy Service**: Authenticated image serving for fallback scenarios
- **Batch Operations**: Support for multiple image uploads per order

#### Data Model (sylvia/models.py)
- **OrderMRNImage**: Complete image metadata with foreign key relationship to orders
- **Image Types**: Enumerated choices for different proof document types
- **Storage Metadata**: Original filename, file size, content type, and storage key tracking
- **Timestamps**: Upload timestamp and modification tracking

### API Endpoints

#### Image Management
- `GET /api/v1/mrn-images/` - List all MRN images (filtered by user permissions)
- `POST /api/v1/mrn-images/` - Create new image record
- `GET /api/v1/mrn-images/{id}/` - Get image details
- `PUT/PATCH /api/v1/mrn-images/{id}/` - Update image metadata
- `DELETE /api/v1/mrn-images/{id}/` - Delete image from both database and cloud storage
- `GET /api/v1/mrn-images/{id}/serve_image/` - Proxy image serving with authentication

#### Order Integration
- `POST /api/v1/orders/{id}/upload_mrn_image/` - Upload image directly to specific order
- `GET /api/v1/orders/{id}/mrn_images/` - Get all images for specific order

#### Utility Endpoints
- `POST /api/v1/mrn-images/{id}/set_primary/` - Set image as primary proof for order
- `GET /api/v1/mrn-images/by_order/?order_id=N` - Filter images by order
- `GET /api/v1/mrn-images/by_type/?type=MRN_PROOF` - Filter images by type

### Security Features
- **Authentication Required**: All endpoints require valid authentication token
- **AWS Signature Version 4**: Industry-standard cloud storage authentication
- **Presigned URLs**: Secure, temporary access without exposing storage credentials
- **File Validation**: Comprehensive validation prevents malicious file uploads
- **Audit Logging**: Complete tracking of all image operations for accountability
- **Permission-Based Access**: Users can only access images for orders they have permission to view

### Cloud Storage Configuration

#### Environment Variables
- `KRUTRIM_STORAGE_ACCESS_KEY`: Krutrim Storage access key
- `KRUTRIM_STORAGE_API_KEY`: Krutrim Storage API key (used as secret key)
- `KRUTRIM_STORAGE_ENDPOINT`: Krutrim Storage endpoint URL
- `KRUTRIM_STORAGE_BUCKET`: Storage bucket name for MRN images
- `KRUTRIM_STORAGE_REGION`: Storage region (default: in-bangalore-1)

#### Data Model Example
```json
{
  "id": 1,
  "order": 15,
  "image_url": "https://blr1.kos.olakrutrimsvc.com/mrn-receipts-datastore/sylvia/orders/ORD000031/mrn_images/abc123_proof.jpg",
  "secure_image_url": "https://blr1.kos.olakrutrimsvc.com/mrn-receipts-datastore/sylvia/orders/ORD000031/mrn_images/abc123_proof.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "image_type": "MRN_PROOF",
  "original_filename": "mrn_proof_photo.jpg",
  "file_size": 2048576,
  "upload_timestamp": "2024-01-01T10:00:00Z",
  "description": "MRN completion proof photo",
  "is_primary": true,
  "storage_key": "sylvia/orders/ORD000031/mrn_images/abc123_mrn_proof_photo.jpg",
  "content_type": "image/jpeg",
  "created_by": {
    "id": 1,
    "username": "admin"
  }
}
```

## MemoTab Cash Collection System

### Business Workflow
1. **Source Management**: Create and manage cash collection sources (e.g., "Cash Counter", "Online Payment", "Bank Transfer")
2. **Cash Collection Recording**: Record daily cash collections with source, amount, receiver, and notes
3. **Analytics & Reporting**: View collection statistics by date range, source, and receiver
4. **Security**: Role-based access control ensures users see only relevant data

### API Endpoints

#### Authentication
All MemoTab APIs require authentication via token or session. Use the same auth endpoints as the main API:
- `POST /api/v1/auth/login/` - Get authentication token

#### Sources API
- `GET /api/v1/memotab/sources/` - List all sources (filtered by user permissions)
- `POST /api/v1/memotab/sources/` - Create new source
- `GET /api/v1/memotab/sources/{id}/` - Get source details
- `PUT/PATCH /api/v1/memotab/sources/{id}/` - Update source
- `DELETE /api/v1/memotab/sources/{id}/` - Delete source
- `GET /api/v1/memotab/sources/active/` - List only active sources
- `POST /api/v1/memotab/sources/{id}/toggle_active/` - Toggle source active status

#### Cash Collections API
- `GET /api/v1/memotab/cash-collections/` - List collections (filtered by user permissions)
- `POST /api/v1/memotab/cash-collections/` - Create new collection record
- `GET /api/v1/memotab/cash-collections/{id}/` - Get collection details
- `PUT/PATCH /api/v1/memotab/cash-collections/{id}/` - Update collection
- `DELETE /api/v1/memotab/cash-collections/{id}/` - Delete collection
- `GET /api/v1/memotab/cash-collections/today/` - Today's collections
- `GET /api/v1/memotab/cash-collections/by_date_range/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Filter by date range
- `GET /api/v1/memotab/cash-collections/by_source/?source_id=N` - Filter by source
- `GET /api/v1/memotab/cash-collections/stats/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Collection statistics

#### Users API
- `GET /api/v1/memotab/users/` - List active users (for cash collection assignment)

### Data Models

#### Source Model
```json
{
  "id": 1,
  "text": "Cash Counter - Main Office",
  "is_active": true,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "created_by": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

#### Cash Collection Model
```json
{
  "id": 1,
  "date": "2024-01-01",
  "amount": "5000.00",
  "note": "Daily cash collection from sales",
  "source": {
    "id": 1,
    "text": "Cash Counter - Main Office"
  },
  "received_by": {
    "id": 2,
    "username": "cashier",
    "email": "cashier@example.com"
  },
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "created_by": {
    "id": 1,
    "username": "admin"
  }
}
```

### Security Features
- **Authentication Required**: All endpoints require valid authentication token
- **Role-Based Access**: Staff users see all data, regular users see only their involvement
- **Data Isolation**: Non-staff users can only access:
  - Sources they created
  - Cash collections they created or received
- **Audit Trail**: All records include created_by and timestamps for accountability

## Development Best Practices

- **Version Control Practices**:
  - Commit changes with descriptive summaries
  - Clearly explain the purpose and impact of each change in commit messages
  - Use concise but informative commit descriptions that help other developers understand the context of the modification

## Database Configuration

- **Development**: SQLite (db.sqlite3)
- **Production**: PostgreSQL via DATABASE_URL environment variable
- Auto-migration on deployment
- Timezone: Asia/Kolkata

## Key Environment Variables

- `DJANGO_SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (True/False)
- `DATABASE_URL`: PostgreSQL connection string (production)
- `RAILWAY_ENVIRONMENT`: Deployment environment
- `ANTHROPIC_API_KEY`: API key for Claude AI integration (dispatch table processing)
- `KRUTRIM_STORAGE_ACCESS_KEY`: Krutrim Storage access key for cloud file storage
- `KRUTRIM_STORAGE_API_KEY`: Krutrim Storage API key (used as secret key)
- `KRUTRIM_STORAGE_ENDPOINT`: Krutrim Storage endpoint URL
- `KRUTRIM_STORAGE_BUCKET`: Storage bucket name for MRN images
- `KRUTRIM_STORAGE_REGION`: Storage region (default: in-bangalore-1)

[Rest of the content remains the same...]
- always use python3 to run commands