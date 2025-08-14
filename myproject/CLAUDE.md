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

## Business Workflow

1. **Order Creation**: Create orders with dealer, vehicle, depot, and products
2. **AI-Powered Dispatch Processing**: Upload dispatch table images for automated order extraction
3. **MRN Process**: Quality check and approval workflow
4. **Billing**: Invoice generation and payment tracking
5. **Analytics**: Performance tracking and reporting with enhanced filtering
6. **Proactive Dealer Management**: Daily recommendations for dealer outreach with complete order history

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

[Rest of the content remains the same...]