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
- **DealerContext**: AI-enhanced relationship management with psychological assessment

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
2. **AI-Powered Dispatch Processing**: Upload dispatch table images for automated order extraction
3. **MRN Process**: Quality check and approval workflow
4. **Billing**: Invoice generation and payment tracking
5. **Analytics**: Performance tracking and reporting with enhanced filtering
6. **Proactive Dealer Management**: Daily recommendations for dealer outreach with complete order history

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