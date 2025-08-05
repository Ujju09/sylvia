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
- **AI-Powered Dispatch Table Processing**: Upload and process dispatch table images using Claude AI
- **Content Security Policy (CSP)**: Enhanced security headers for web application protection
- **Secure Cookie Configuration**: Implementation of secure session management
- **Proactive Dashboard Analytics**: Advanced dealer contact recommendations with intelligent scoring
- **Mixed Active/Dormant Dealer Targeting**: Balanced approach to maintain existing relationships and re-engage dormant customers

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

### AI-Powered Features
- `/orders/dispatch-table/` - Upload and process dispatch table images using Claude AI
- `/orders/process-dispatch-image/` - Process uploaded dispatch table images
- `/orders/confirm-dispatch-data/` - Confirm extracted dispatch data before order creation
- `/orders/create-dispatch-orders/` - Create orders from processed dispatch data

## API Endpoints

Base URL: `/api/v1/`
- Dealers, Products, Vehicles, Depots, Orders, MRNs, Invoices
- Dashboard stats and analytics endpoints
- Search and filtering capabilities
- Pagination enabled (20 items per page)

### DealerContext API (`/api/v1/dealer-context/`)
**Read and Create Operations Only** - Update and delete operations are disabled for audit trail integrity.

#### Standard Endpoints:
- `GET /api/v1/dealer-context/` - List all dealer contexts (paginated)
- `POST /api/v1/dealer-context/` - Create new dealer context
- `GET /api/v1/dealer-context/{id}/` - Get specific dealer context

#### Custom Actions:
- `GET /api/v1/dealer-context/by_dealer/?dealer_id={id}` - Get all contexts for specific dealer
- `GET /api/v1/dealer-context/follow_ups_due/` - Get contexts with overdue follow-ups
- `GET /api/v1/dealer-context/high_priority/` - Get high/critical priority contexts
- `GET /api/v1/dealer-context/recent_interactions/` - Get interactions from last 7 days

#### Filtering and Search:
- **Search fields**: dealer name/code, interaction summary, detailed notes, tags, topics
- **Filter fields**: dealer, interaction_type, sentiment, priority_level, follow_up_required, issue_resolved
- **Ordering**: interaction_date, dealer name, priority_level, sentiment

#### Key Features:
- Structured trait evaluation (1-10 scale) for business and relationship assessment
- Understanding-focused fields for deep dealer insights
- Follow-up tracking and priority management
- AI insights and psychological assessment integration
- JSON fields for flexible data storage (topics_discussed, tags)

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

### Order List UI
- Enhanced filtering capabilities for better data organization
- Brief statistics display for quick insights
- Improved navigation and user experience

### AI-Powered Dispatch Processing
- Image upload interface for dispatch table processing
- AI-powered data extraction using Claude API
- Confirmation workflow before order creation
- Error handling and validation for processed data
- Logging system for troubleshooting and audit trails

### Proactive Analytics Dashboard
- **Daily Dealer Contact Recommendations**: AI-powered scoring system suggests 2-3 dealers to contact daily
- **Active vs Dormant Dealer Mix**: Intelligent algorithm ensures mix of relationship maintenance and re-engagement
- **Comprehensive Order History**: Shows dealer's popular products, order frequency, and recent quantities
- **Multiple Display Formats**: 
  - Compact card view with expandable details
  - Comprehensive table view with complete dealer analysis
  - Product history with total quantities and order patterns
- **Smart Scoring Algorithm**: 
  - Factors in order frequency, recency, volume, and historical patterns
  - Prioritizes dormant high-value customers for re-engagement
  - Maintains regular contact schedules for active dealers
- **Product Purchase Patterns**: Displays most-ordered products with quantities for strategic conversations

## Security Features

### Content Security Policy (CSP)
- Comprehensive CSP headers implementation
- Protection against XSS attacks
- Restricted resource loading policies
- Frame protection and click-jacking prevention

### Secure Configuration
- Secure cookie settings
- HTTPS enforcement in production
- CSRF protection
- Proxy SSL header configuration for Railway deployment

## Dependencies

### Core Requirements
- Django 5.2.4 with REST Framework
- PostgreSQL support (psycopg2-binary)
- WhiteNoise for static files
- Gunicorn for production serving

### AI Integration
- Anthropic Claude API (anthropic==0.40.0)
- Image processing capabilities
- JSON data extraction and validation

### Security & Utilities
- django-csp for Content Security Policy
- django-cors-headers for CORS handling
- python-dotenv for environment management
- Report generation (openpyxl, reportlab, pandas)

## Implementation Details

### Proactive Dashboard Implementation (orders/views.py)
The proactive analytics system is implemented in the `analytics()` view with the following key components:

#### Dealer Recommendation Algorithm
- **Scoring System**: Multi-factor scoring based on order frequency, recency, volume, and historical patterns
- **Active/Dormant Classification**: Dealers classified as dormant if no orders in 35+ days or reduced frequency
- **Mixed Recommendations**: Algorithm ensures minimum 1 dormant dealer in daily recommendations (if available)
- **Randomization**: Daily seed-based randomization prevents showing same dealers repeatedly

#### Product History Aggregation
- **Manual Aggregation**: Uses Python collections.defaultdict for reliable product quantity totals
- **Tuple-based Storage**: Product data stored as (product_name, total_quantity) tuples for template compatibility
- **Fallback Text**: String-based product summary for reliable display across different UI contexts

#### Template Integration (orders/templates/orders/analytics.html)
- **Multiple Display Modes**: 
  - Inline badges for quick product overview
  - Expandable detailed history sections
  - Complete dealer analysis table
- **Responsive Design**: Full-width layouts with Bootstrap-based responsive components
- **Conditional Display**: Handles edge cases like dealers with no order history

#### Data Structure
```python
dealer_data = {
    'dealer': dealer_object,
    'score': calculated_priority_score,
    'popular_products': [(product_name, total_quantity), ...],
    'product_summary_text': "Product1 (45MT), Product2 (30MT)",
    'monthly_frequency': avg_orders_per_month,
    'is_dormant': boolean_dormant_status,
    # ... additional metrics
}
```