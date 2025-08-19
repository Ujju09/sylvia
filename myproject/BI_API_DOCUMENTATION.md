# Business Intelligence API Documentation

This document provides comprehensive documentation for the Business Intelligence (BI) API endpoints designed specifically for the Next.js dashboard implementation.

## Base URL
```
https://sylvia-production.up.railway.app/api/v1/bi/
```

## Authentication
All BI endpoints require authentication using Token-based auth:

```http
Authorization: Token your-auth-token-here
```

## Common Query Parameters

Most endpoints support these common filters:

- `depot_id`: Filter by specific depot (use `all` for all depots)
- `start_date`: Start date in YYYY-MM-DD format
- `end_date`: End date in YYYY-MM-DD format
- `include_stock`: Include stock orders (anonymous dealer orders) - `true`/`false`

---

## 1. Executive Summary API

**Endpoint**: `GET /api/v1/bi/executive-summary/`

**Purpose**: Main dashboard KPIs and overview metrics

### Query Parameters
- `depot_id` (optional): Specific depot ID or `all`
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)

### Example Request
```http
GET /api/v1/bi/executive-summary/?depot_id=1&start_date=2024-01-01&end_date=2024-12-31
Authorization: Token your-token-here
```

### Response Structure
```json
{
  "date_range": "2024-01-01 to 2024-12-31",
  "depot_filter": "Nagar Untari Depot",
  "kpis": {
    "total_orders": 1250,
    "stock_orders": 320,
    "regular_orders": 930,
    "total_quantity_billed": 15420.5,
    "active_vehicles": 45,
    "vehicles_with_stock": 12,
    "completion_rate": 89.5
  },
  "trends": {
    "orders_month_over_month": 12.5,
    "quantity_month_over_month": 8.3,
    "efficiency_trend": "improving"
  }
}
```

### Usage in Next.js
```javascript
const fetchExecutiveSummary = async (depotId = 'all', dateRange = null) => {
  const params = new URLSearchParams({
    depot_id: depotId,
    ...(dateRange && {
      start_date: dateRange.start,
      end_date: dateRange.end
    })
  });
  
  const response = await fetch(`/api/v1/bi/executive-summary/?${params}`, {
    headers: {
      'Authorization': `Token ${authToken}`,
      'Content-Type': 'application/json'
    }
  });
  
  return await response.json();
};
```

---

## 2. Stock Analytics API

**Endpoint**: `GET /api/v1/bi/stock-analytics/`

**Purpose**: All stock-related analytics (orders where dealer is "Anonymous")

### Query Parameters
- `depot_id` (optional): Specific depot ID or `all`
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `product_ids[]` (optional): Array of product IDs to filter

### Example Request
```http
GET /api/v1/bi/stock-analytics/?depot_id=all&product_ids[]=1&product_ids[]=2
Authorization: Token your-token-here
```

### Response Structure
```json
{
  "stock_summary": {
    "total_stock_orders": 320,
    "total_stock_quantity": 4250.5,
    "vehicles_carrying_stock": 12,
    "average_stock_per_vehicle": 354.2
  },
  "stock_by_depot": [
    {
      "depot_id": 1,
      "depot_name": "Nagar Untari Depot",
      "stock_orders": 45,
      "stock_quantity": 650.5,
      "vehicles_count": 3,
      "percentage_of_total": 15.3
    }
  ],
  "stock_by_product": [
    {
      "product_name": "Magna",
      "stock_quantity": 1250.5,
      "percentage": 29.4
    }
  ],
  "vehicles_with_stock": [
    {
      "vehicle_id": 15,
      "truck_number": "CG15EA0464",
      "depot_name": "Nagar Untari Depot",
      "stock_quantity": 125.5,
      "last_updated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## 3. Monthly Trends API

**Endpoint**: `GET /api/v1/bi/monthly-trends/`

**Purpose**: Month-on-month analysis for charts and trend visualization

### Query Parameters
- `depot_id` (optional): Specific depot ID or `all`
- `granularity` (optional): `monthly` (default) or `weekly`
- `months_back` (optional): Number of months to include (default: 12)
- `include_stock` (optional): Include stock orders - `true`/`false` (default: true)

### Example Request
```http
GET /api/v1/bi/monthly-trends/?depot_id=1&months_back=6&include_stock=true
Authorization: Token your-token-here
```

### Response Structure
```json
{
  "quantity_billed_trends": [
    {
      "month": "2024-01",
      "total_quantity": 1250.5,
      "by_depot": [
        {
          "depot_name": "Nagar Untari Depot",
          "quantity": 425.2
        }
      ],
      "by_product": [
        {
          "product_name": "Magna",
          "quantity": 380.5
        }
      ]
    }
  ],
  "order_trends": [
    {
      "month": "2024-01",
      "total_orders": 125,
      "stock_orders": 32,
      "regular_orders": 93
    }
  ],
  "depot_performance": [
    {
      "depot_name": "Nagar Untari Depot",
      "monthly_data": [
        {
          "month": "2024-01",
          "orders": 45,
          "quantity": 425.2,
          "efficiency_score": 92.5
        }
      ]
    }
  ]
}
```

### Usage for Charts in Next.js
```javascript
const prepareChartData = (trendsData) => {
  const labels = trendsData.quantity_billed_trends.map(item => item.month);
  const quantities = trendsData.quantity_billed_trends.map(item => item.total_quantity);
  
  return {
    labels,
    datasets: [{
      label: 'Quantity Billed (MT)',
      data: quantities,
      backgroundColor: 'rgba(54, 162, 235, 0.2)',
      borderColor: 'rgba(54, 162, 235, 1)',
      borderWidth: 1
    }]
  };
};
```

---

## 4. Depot Analytics API

**Endpoint**: `GET /api/v1/bi/depot-analytics/`

**Purpose**: All data categorized by depots for depot comparison

### Query Parameters
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `include_stock` (optional): Include stock orders - `true`/`false` (default: true)

### Example Request
```http
GET /api/v1/bi/depot-analytics/?start_date=2024-01-01&include_stock=true
Authorization: Token your-token-here
```

### Response Structure
```json
{
  "depot_summary": [
    {
      "depot_id": 1,
      "depot_name": "Nagar Untari Depot",
      "total_orders": 245,
      "stock_orders": 45,
      "regular_orders": 200,
      "total_quantity": 3250.5,
      "active_vehicles": 12,
      "completion_rate": 94.2,
      "top_products": [
        {
          "product_name": "Magna",
          "quantity": 850.5
        }
      ],
      "monthly_performance": [
        {
          "month": "2024-01",
          "orders": 45,
          "quantity": 425.2
        }
      ]
    }
  ],
  "depot_comparison": {
    "performance_matrix": [
      {
        "depot_name": "Nagar Untari Depot",
        "orders_rank": 1,
        "quantity_rank": 2,
        "efficiency_rank": 1
      }
    ]
  }
}
```

---

## 5. Operations Live API

**Endpoint**: `GET /api/v1/bi/operations-live/`

**Purpose**: Real-time operational data for live dashboard updates

### Query Parameters
None - always returns current day and real-time data

### Example Request
```http
GET /api/v1/bi/operations-live/
Authorization: Token your-token-here
```

### Response Structure
```json
{
  "today_metrics": {
    "orders_created": 15,
    "stock_orders_created": 4,
    "mrn_completed": 8,
    "orders_billed": 12,
    "vehicles_loaded": 18
  },
  "pending_actions": {
    "pending_mrn": 25,
    "pending_billing": 18,
    "overdue_orders": 3
  },
  "active_vehicles": [
    {
      "truck_number": "CG15EA0464",
      "depot": "Nagar Untari Depot",
      "status": "carrying_stock",
      "quantity": 125.5
    }
  ]
}
```

---

## Stock Orders Identification

**Key Concept**: Orders where `dealer.name = "Anonymous"` represent stock/inventory orders, not customer orders.

### Stock vs Regular Orders
- **Stock Orders**: `dealer.name = "Anonymous"` - represents inventory/stock movement
- **Regular Orders**: All other orders with actual dealer names - represents customer orders

---

## Next.js Implementation Examples

### 1. Dashboard Hook
```javascript
import { useState, useEffect } from 'react';

export const useBIDashboard = (depotId = 'all', dateRange = null) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/v1/bi/executive-summary/', {
          headers: {
            'Authorization': `Token ${getAuthToken()}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) throw new Error('Failed to fetch data');
        
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [depotId, dateRange]);

  return { data, loading, error };
};
```

### 2. Stock Dashboard Component
```javascript
import React from 'react';
import { useBIStock } from '../hooks/useBIStock';

const StockDashboard = ({ depotId = 'all' }) => {
  const { data, loading, error } = useBIStock(depotId);

  if (loading) return <div>Loading stock data...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="stock-dashboard">
      <div className="stock-summary">
        <h3>Stock Overview</h3>
        <div className="metrics-grid">
          <div className="metric">
            <span className="label">Total Stock Orders</span>
            <span className="value">{data.stock_summary.total_stock_orders}</span>
          </div>
          <div className="metric">
            <span className="label">Total Stock Quantity</span>
            <span className="value">{data.stock_summary.total_stock_quantity} MT</span>
          </div>
          <div className="metric">
            <span className="label">Vehicles with Stock</span>
            <span className="value">{data.stock_summary.vehicles_carrying_stock}</span>
          </div>
        </div>
      </div>
      
      <div className="stock-by-depot">
        <h3>Stock by Depot</h3>
        {data.stock_by_depot.map(depot => (
          <div key={depot.depot_id} className="depot-item">
            <span>{depot.depot_name}</span>
            <span>{depot.stock_quantity} MT ({depot.percentage_of_total}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

### 3. Auto-refresh for Real-time Data
```javascript
import { useEffect, useState } from 'react';

export const useRealTimeOperations = (refreshInterval = 30000) => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchOperationsData = async () => {
      try {
        const response = await fetch('/api/v1/bi/operations-live/', {
          headers: {
            'Authorization': `Token ${getAuthToken()}`,
            'Content-Type': 'application/json'
          }
        });
        const result = await response.json();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch operations data:', error);
      }
    };

    // Initial fetch
    fetchOperationsData();

    // Set up auto-refresh
    const interval = setInterval(fetchOperationsData, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  return data;
};
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid or missing token)
- `500`: Internal Server Error

Error responses follow this format:
```json
{
  "error": "Error message description",
  "detail": "Additional error details if available"
}
```

---

## Performance Considerations

1. **Caching**: Consider implementing client-side caching for data that doesn't change frequently
2. **Pagination**: Large datasets are automatically limited (e.g., top 20 vehicles)
3. **Real-time Updates**: Use the operations-live endpoint sparingly to avoid overwhelming the server
4. **Date Ranges**: Limit date ranges to reasonable periods (e.g., 1 year max) for better performance

---

## Testing the APIs

You can test these APIs using curl:

```bash
# Test executive summary
curl -H "Authorization: Token your-token-here" \
     "https://your-domain.com/api/v1/bi/executive-summary/"

# Test stock analytics with filters
curl -H "Authorization: Token your-token-here" \
     "https://your-domain.com/api/v1/bi/stock-analytics/?depot_id=1&start_date=2024-01-01"
```

This API architecture provides your Next.js dashboard with optimally structured data for creating comprehensive business intelligence visualizations and insights.