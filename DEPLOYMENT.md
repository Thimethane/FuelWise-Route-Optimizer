# Deployment & Testing Guide

## Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
cd fuel_route_optimizer
pip install -r requirements.txt
```

### 2. Initialize Database
```bash
# Run migrations
python manage.py makemigrations routing
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional, for admin)
python manage.py createsuperuser
```

### 3. Import Fuel Data
```bash
# Copy your CSV file to project directory
cp /path/to/fuel-prices-for-be-assessment.csv ./fuel_prices.csv

# Import stations
### 1. Production Geocoding

####Import the CSV and geocode stations using the real geocoding API, it will take more than 2 hours:

```bash
python manage.py import_fuel_data file.csv --geocode
python manage.py import_fuel_data fuel_prices.csv --geocode --use-mock #For quickdemo
# Expected output:
# Cleared existing fuel stations
# Importing fuel stations from fuel_prices.csv
# Imported 1000 stations...
# Imported 2000 stations...
# ...
# Successfully imported 6,738 fuel stations
```

**Note on Geocoding:**
- The import command accepts a `--geocode` flag to add lat/lng coordinates
- This uses Nominatim API (free, 1 req/sec limit)
- For 6,738(duplicates are removed) stations: ~2.5 hours
- **For this demo**: Skip geocoding, use mock coordinates
- Mock client will generate realistic coordinates automatically

### 4. Start Server
```bash
python manage.py runserver

# Server running at http://localhost:8000
```

### 5. Test API
```bash
# Quick health check
curl http://localhost:8000/api/health/

# Test route optimization
curl -X POST http://localhost:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "finish": "Los Angeles, CA"}'
```

---

## Testing with Postman

### Import Collection
1. Open Postman
2. Click "Import"
3. Select `Fuel_Route_Optimizer.postman_collection.json`
4. Collection appears with 8 pre-configured requests

### Test Scenarios

**Scenario 1: Short Route** (380 miles, 0-1 stop)
```
Request: San Francisco → Los Angeles
Expected: 0-1 fuel stops, ~$130 total
Response time: <500ms
```

**Scenario 2: Medium Route** (1,100 miles, 2-3 stops)
```
Request: Chicago → Houston
Expected: 2-3 fuel stops, ~$380 total
Response time: <800ms
```

**Scenario 3: Long Route** (2,900 miles, 5-6 stops)
```
Request: San Francisco → New York
Expected: 5-6 fuel stops, ~$1,000 total
Response time: <1200ms
```

### What to Look For

✅ **Performance Metrics**
- `computation_time`: Should be <1.5s
- `map_api_calls`: Should be 1 (or 0 if cached)

✅ **Optimization Quality**
- Fuel stops should be 300-450 miles apart
- Prices should be competitive (lowest available near route)
- Total cost should be reasonable

✅ **Response Structure**
- All required fields present
- Coordinates are valid US locations
- Math checks out (fuel_needed × price = cost)

---

## Performance Testing

### Load Test Script
```python
import requests
import time
import statistics

def test_performance():
    url = "http://localhost:8000/api/optimize-route/"
    routes = [
        {"start": "San Francisco, CA", "finish": "Los Angeles, CA"},
        {"start": "Chicago, IL", "finish": "Houston, TX"},
        {"start": "New York, NY", "finish": "Miami, FL"},
    ]
    
    times = []
    
    for route in routes * 3:  # Test each route 3 times
        start = time.time()
        response = requests.post(url, json=route)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            times.append(elapsed)
            print(f"✓ {route['start']} → {route['finish']}: {elapsed:.3f}s")
        else:
            print(f"✗ Failed: {response.status_code}")
    
    print(f"\nPerformance Summary:")
    print(f"  Average: {statistics.mean(times):.3f}s")
    print(f"  Median: {statistics.median(times):.3f}s")
    print(f"  Min: {min(times):.3f}s")
    print(f"  Max: {max(times):.3f}s")

if __name__ == "__main__":
    test_performance()
```

Run with:
```bash
python test_performance.py
```

Expected output:
```
✓ San Francisco, CA → Los Angeles, CA: 0.342s
✓ Chicago, IL → Houston, TX: 0.289s
✓ New York, NY → Miami, FL: 0.315s
...
Performance Summary:
  Average: 0.312s
  Median: 0.305s
  Min: 0.289s
  Max: 0.342s
```

---

## Production Deployment

### Environment Setup

**1. Create .env file:**
```bash
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost:5432/fuel_optimizer
REDIS_URL=redis://localhost:6379/0
```

**2. Update settings.py:**
```python
import os
from pathlib import Path
import dj_database_url

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL')
    )
}

# Redis cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations
RUN python manage.py migrate

EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "fuel_route_optimizer.wsgi:application"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/fuel_optimizer
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./media:/app/media

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=fuel_optimizer
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

**Deploy:**
```bash
docker-compose up -d
```

### Cloud Deployment (GCP)

**1. Build and push:**
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/fuel-optimizer

gcloud run deploy fuel-optimizer \
  --image gcr.io/PROJECT_ID/fuel-optimizer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

**2. Connect Cloud SQL:**
```bash
gcloud sql instances create fuel-optimizer-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud run services update fuel-optimizer \
  --add-cloudsql-instances PROJECT_ID:us-central1:fuel-optimizer-db
```

---

## Monitoring & Logging

### Application Logs
```bash
# View logs
tail -f debug.log

# Filter for errors
grep ERROR debug.log

# Performance analysis
grep "Optimization complete" debug.log | awk '{print $NF}'
```

### Health Monitoring
```bash
# Set up health check
curl http://localhost:8000/api/health/

# Expected response:
{
  "status": "healthy",
  "database": {
    "connected": true,
    "fuel_stations": 8152
  },
  "cache": {
    "connected": true
  },
  "version": "1.0.0"
}
```

### Performance Metrics
```python
# Add to views.py for detailed metrics
import time
from django.core.cache import cache

def track_performance(view_func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = view_func(*args, **kwargs)
        duration = time.time() - start
        
        # Store in cache for monitoring
        key = f"perf:{view_func.__name__}"
        metrics = cache.get(key, [])
        metrics.append(duration)
        cache.set(key, metrics[-100:], timeout=3600)  # Keep last 100
        
        return result
    return wrapper
```

---

## Troubleshooting

### Common Issues

**Issue: "No fuel stations found near route"**
```
Cause: Database empty or coordinates missing
Fix: Run import command with --geocode flag
```

**Issue: Slow response times**
```
Cause: Cache not working or DB not indexed
Fix:
1. Check cache: python manage.py shell
   >>> from django.core.cache import cache
   >>> cache.set('test', 'value')
   >>> cache.get('test')
2. Check indexes: python manage.py dbshell
   >>> EXPLAIN ANALYZE SELECT * FROM fuel_stations WHERE ...
```

**Issue: "Location not found"**
```
Cause: Invalid location string
Fix: Use format "City, State" or full address
Examples:
  ✓ "San Francisco, CA"
  ✓ "1600 Amphitheatre Parkway, Mountain View, CA"
  ✗ "SF" (too ambiguous)
```

### Debug Mode

Enable verbose logging:
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'routing': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

---

## API Rate Limits

**External APIs Used:**

1. **Nominatim (Geocoding)**
   - Free tier: 1 request/second
   - Caching strategy: 24 hour TTL
   - Impact: Minimal (2 calls max per route)

2. **OSRM (Routing)**
   - Free tier: No official limit
   - Caching strategy: 1 hour TTL
   - Impact: 1 call per route

**Optimization:**
- First request: 1-3 external calls
- Subsequent requests: 0 calls (all cached)
- Cache hit rate: >90% after warmup

---

## Code Quality Checklist

✅ **Django Best Practices**
- Models with proper validation
- DRF serializers for API contracts
- Proper error handling
- Database indexes
- Logging throughout

✅ **Performance**
- Query optimization
- Spatial indexing
- Response caching
- Bulk operations

✅ **Production Ready**
- Environment configuration
- Health checks
- Monitoring setup
- Docker support
- Comprehensive docs

---

## Support

If you encounter issues:
1. Check troubleshooting section above
2. Review logs: `tail -f debug.log`
3. Test with Postman collection
4. Contact: timotheeringuyeneza@gmail.com
