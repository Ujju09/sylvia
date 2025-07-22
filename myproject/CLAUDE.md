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

### API Architecture (sylvia/)
- RESTful API using Django REST Framework
- Token-based authentication
- ViewSets for CRUD operations
- Custom actions for business workflows
- Comprehensive analytics endpoints

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
2. **MRN Process**: Quality check and approval workflow
3. **Billing**: Invoice generation and payment tracking
4. **Analytics**: Performance tracking and reporting

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

## Static Files

- Using WhiteNoise for static file serving
- Static files collected to `staticfiles/`
- Admin assets included
- Custom CSS and JS in `orders/static/`

## Authentication & Permissions

- Django built-in authentication
- Login required for all views
- Token authentication for API
- Session authentication for web interface

## Key Features

- Auto-generated order numbers with date-based format
- Dealer management with credit limits and terms
- Vehicle tracking with capacity management
- Quality control via MRN approval workflow
- Comprehensive analytics and reporting
- Excel/PDF export capabilities
- Audit logging for important actions

## Testing

No specific test framework configured. To add tests, create test files in each app and run:
```bash
python3 manage.py test
```

## Web UI Endpoints

### Order Management
- `/orders/` - Order list and workflow
- `/orders/order-workflow/` - Create new orders
- `/orders/update-order/<id>/` - Update order status (MRN, billing)
- `/orders/analytics/` - Analytics dashboard
- `/orders/export-analytics/` - Export data (Excel/PDF)

### Vehicle Management  
- `/orders/vehicles/` - Vehicle list with search/filter
- `/orders/vehicles/add/` - Add new vehicle
- `/orders/vehicles/edit/<id>/` - Edit vehicle
- `/orders/vehicles/delete/<id>/` - Delete vehicle confirmation

### Dealer Management
- `/orders/dealers/` - Dealer list with search/filter  
- `/orders/dealers/add/` - Add new dealer
- `/orders/dealers/edit/<id>/` - Edit dealer
- `/orders/dealers/delete/<id>/` - Delete dealer confirmation

### Entity Forms
- `/orders/products/add/` - Add new product
- `/orders/depots/add/` - Add new depot

## API Endpoints

Base URL: `/api/v1/`
- Dealers, Products, Vehicles, Depots, Orders, MRNs, Invoices
- Dashboard stats and analytics endpoints
- Search and filtering capabilities
- Pagination enabled (20 items per page)

## UI Features

### Vehicle Management UI
- Complete CRUD operations with responsive design
- Search by truck number, owner, driver name
- Filter by status (active/inactive) and vehicle type
- Statistics display (total vehicles, capacity, etc.)
- Form validation with proper error handling

### Dealer Management UI  
- Complete CRUD operations with comprehensive forms
- Search by name, code, contact person, phone, email, city
- Filter by active/inactive status
- Business information management (GSTIN, credit terms)
- Address and contact information organization
- Statistics display (total dealers, credit limits, etc.)
- Delete confirmation with full dealer details