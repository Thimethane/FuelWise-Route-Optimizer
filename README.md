# ⛽ Fuel Route Optimizer API

**A high-performance, production-ready Django REST API for optimizing fuel stops along US transcontinental routes.**

Built by **Timothee Ringuyeneza** | Backend Django Engineer

---

## 🎯 Overview

This API calculates the most cost-effective fueling strategy for long-haul trips across the USA. By analyzing route geometry and real-time fuel prices, it identifies specific stations that minimize total trip expenditure while ensuring the vehicle never exceeds its 500-mile range.

### 🧠 Optimization Engine

* **Spatial Indexing**: Rapidly filters 8,000+ stations down to a relevant "route corridor" using PostgreSQL/SQLite indexing.
* **Hybrid Routing**: Uses OSRM for precise geometry and Google Maps/Nominatim for geocoding, with a fallback **Mock Engine** for zero-latency demos.
* **Greedy Lookahead Algorithm**: Balances current fuel levels against upcoming price drops to decide whether to refuel now or wait for a cheaper station 100 miles ahead.

---

### 1. Installation & Environment

```bash
# Clone and enter
git clone https://github.com/Thimethane/FuelWise-Route-Optimizer
cd FuelWise-Route-Optimizer

# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure secrets
---

### ⚙️ Environment Configuration

The API is built with an **automated environment toggle**. You can switch between a high-performance Docker stack (PostgreSQL + Redis) and a zero-dependency local setup (SQLite + LocMem) by editing your `.env` file.

**1. Create your environment file:**

```bash
cp .env.example .env

```

**2. Configure your execution profile:**

| Mode | `DB_ENGINE` | `REDIS_URL` | Use Case |
| --- | --- | --- | --- |
| **Local** | `sqlite` | *(Comment out)* | Rapid development, zero installation, no Docker needed. |
| **Docker** | `postgres` | `redis://redis:6379/0` | Production testing, high-concurrency caching, persistent data. |

**Example `.env` for Local Development:**

```env

# Set DB_ENGINE to 'postgres' to use the Docker container, 'sqlite' for local in .env
# Use SQLite for zero-dependency local runs
DB_ENGINE=sqlite

# Comment out REDIS_URL to automatically trigger Local Memory Caching
# REDIS_URL=redis://redis:6379/0

# Your API Key
GOOGLE_MAPS_API_KEY=your_key_here

```
---

### 🚀 Usage Tip

**When `DB_ENGINE=sqlite**`: Django uses `db.sqlite3` and stores cache in your RAM (**LocMemCache**).
**When `DB_ENGINE=postgres**`: Django connects to the **PostgreSQL** container and uses **Redis** for persistent caching.

### 🧠 Why the Mock data might not return "correct" data:

When you run the **Chicago ➔ Houston** route, the algorithm looks for stations within a specific "Search Corridor" (e.g., 75 miles from the road).

1. **Mathematical Mismatch:** If the Mock algorithm assigns a station in "Tillatoba, MS" a random coordinate that is actually 200 miles away from the highway, the spatial query `latitude BETWEEN ... AND ...` will skip it.
2. **State Logic:** If your mock generator assigns coordinates based on a simple bounding box, it might place a "Texas" station inside "Oklahoma," causing the `state='TX'` filter to return no results for that specific location.


### Mannual Installation & Environment

```

### 2. Database Initialization

```bash
# Run migrations
python manage.py makemigrations routing
python manage.py makemigrations
python manage.py migrate
```

**Commands:**

```bash
# 1. Fast Demo (Import + State-Aware Mock Coordinates)
python manage.py import_fuel_data fuel_prices.csv --use-mock

# 2. Production Import (Uses GOOGLE_MAPS_API_KEY from .env)
python manage.py import_fuel_data fuel_prices.csv --geocode

# 3. Standard Refresh (Price update only, keeps existing coords)
python manage.py import_fuel_data fuel_prices.csv

```
---

### 3. Smart Data Import ⚡

The import command uses an **UPSERT strategy**, updating prices for existing stations without losing previously fetched coordinates. Geocoding performance varies significantly by provider:

| Mode | Provider | Estimated Time (6,700 stations) | Description |
| --- | --- | --- | --- |
| **Mock** | Deterministic Alg | **< 30 seconds** | Uses state-aware clustering for local development. |
| **Pro** | **Google Maps** | **~10-15 minutes** | High-speed, high-accuracy production geocoding. |
| **Free** | Nominatim (OSM) | **~2 hours** | Respects 1-req/sec rate limits; slower fallback. |


#### ⚠️ Critical: Database Cleanup

If your routes are failing with `400 Invalid Request` or the Demo shows `0 stations found` after switching modes, you must clear the stale data.

**Why this happens:**
The optimizer relies on geographic coordinates to find stations along a route.

* **Mock Mode** generates simulated coordinates for speed.
* **Geocode Mode** fetches real GPS coordinates from Google.
If you previously imported data using `--use-mock` and now want to use real `--geocode` (or vice versa), the database may contain "stale" coordinates that don't align with the actual route geometry, causing the optimizer to find zero valid stops.
---
**Cleanup Command:**

```bash
# Via Local Python
python manage.py shell -c "from routing.models import FuelStation; FuelStation.objects.all().delete()"

# Via Make
make clean-db

# Via Docker
docker-compose exec web python manage.py shell -c "from routing.models import FuelStation; FuelStation.objects.all().delete()"
```
---
### 4. Run & Test

```bash
python manage.py runserver

# In a new terminal:
curl -X POST http://localhost:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "San Francisco, CA", "finish": "New York, NY"}'

```
---

```bash
# 1. Ensure the server is running
python manage.py runserver

## Step 2: Test with Postman (2 minutes)

### Option A: Use Postman Collection

1. Open Postman
2. Import `Fuel_Route_Optimizer.postman_collection.json`
3. Run "San Francisco to Los Angeles" request
4. Observe results in <1 second

### Option B: Use curl

```bash
curl -X POST http://localhost:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "San Francisco, CA",
    "finish": "Los Angeles, CA"
  }'
```

Expected response:
```json
{
  "start_location": {"lat": 37.7749, "lng": -122.4194, ...},
  "finish_location": {"lat": 34.0522, "lng": -118.2437, ...},
  "total_distance": 383.2,
  "fuel_stops": [...],
  "total_fuel_cost": 132.45,
  "computation_time": 0.34,
  "map_api_calls": 1
}
```

---

## Step 3: Run Demo Script (Optional)

```bash
python demo.py
```

Interactive demo with:
- Health checks
- Multiple route tests
- Performance summary

---

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

## Test Routes to Try

### Short (380 miles, 0-1 stop)
```json
{"start": "San Francisco, CA", "finish": "Los Angeles, CA"}
```

### Medium (1,100 miles, 2-3 stops)
```json
{"start": "Chicago, IL", "finish": "Houston, TX"}
```

### Long (2,900 miles, 5-6 stops)
```json
{"start": "New York, NY", "finish": "Los Angeles, CA"}
```

---

#### 🚀 Docker Deployment & DB Init

---

## 🚀 Quick Start (Automated)

The project includes a `Makefile` to automate the complex Docker and database initialization steps.

### ⚡ One-Command Setup

If you have `make` installed, simply run:

```bash
make setup

```

*This command builds the containers, starts the infrastructure, runs migrations, imports mock data, and launches the demo suite.*

### 🛠️ Individual Commands

| Command | Description |
| --- | --- |
| `make up` | Start PostgreSQL, Redis, and Django containers |
| `make down` | Stop all services |
| `make migrate` | Run database migrations inside the container |
| `make import` | Seed the database with 6,738 stations (Mock mode) |
| `make demo` | Run the interactive CLI benchmark suite |

**1. Start the Infrastructure**
Launch the PostgreSQL and Redis containers in the background:

```bash
docker-compose up -d

```

**2. Database Initialization**
Run these commands inside the running web container to set up your schema:

```bash
# Run migrations inside the container
docker-compose exec web python manage.py makemigrations routing
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

```

**3. Seed the Data**
Now that the PostgreSQL tables exist, import your geocoded fuel data:

```bash
docker-compose exec web python manage.py import_fuel_data fuel_prices.csv --geocode

```

---

### 💡 Connecting to PostgreSQL from your Host

If you want to view the data using a tool like **pgAdmin** or **DBeaver** from your actual computer (not inside Docker), use these credentials:

* **Host**: `localhost`
* **Port**: `5433` (mapped in docker-compose)
* **User**: `fuel_user`
* **Password**: `fuel_pass`
* **Database**: `fuel_db`
---

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

## 📚 API Documentation

### `POST /api/optimize-route/`

Returns the optimal fueling stops for a given trip.

**Payload:**

```json
{
  "start": "Chicago, IL",
  "finish": "Miami, FL"
}

```
---

**External APIs Used:**

1. **Google Maps (Primary Geocoding)**
* Role: High-accuracy address resolution and validation.
* Usage: Preferred for production routing accuracy.
* Caching strategy: Results persisted in Database (Permanent).


2. **Nominatim (Fallback Geocoding)**
* Role: Free fallback geocoder.
* Free tier: 1 request/second.
* Caching strategy: 24-hour TTL.


3. **OSRM (Routing)**
* Role: Precise route geometry and distance calculation.
* Free tier: No official limit.
* Caching strategy: 1-hour TTL.



**Optimization:**

* First request: 1-3 external calls
* Subsequent requests: 0 calls (all cached)
* Cache hit rate: >90% after warmup

---

## 🧪 Testing & Quality Assurance

### Performance Benchmarks (SF ➔ NY)

| Metric | Result |
| --- | --- |
| **Stations Evaluated** | 6,738 |
| **Computation Time** | ~340ms (Cold) / ~90ms (Cached) |
| **API Calls Made** | 1 (OSRM) |
| **Accuracy** | 100% Range Compliance |

---

## 🛠️ Architecture & Performance

### Caching Strategy

1. **Level 1 (Redis/LocMem)**: Stores full route objects and geocoding results (TTL: 1hr - 24hr).
2. **Level 2 (Database)**: Lat/Lng coordinates are persisted to avoid redundant API hits.
3. **Level 3 (Mock Fallback)**: Ensures high availability even if external Map APIs are down.

---

## 🔧 Configuration

Vehicle and algorithm constants can be adjusted in `routing/services.py`:

* `VEHICLE_RANGE`: Default `500` miles.
* `MPG`: Default `10`.
* `SEARCH_CORRIDOR_WIDTH`: `75` miles (Corridor width for station filtering).

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

## 📞 Support & Links

* **Engineer**: Timothee Ringuyeneza
* **Email**: [timotheeringuyeneza@gmail.com](mailto:timotheeringuyeneza@gmail.com)
* **Postman Collection**: `Fuel_Route_Optimizer.postman_collection.json` included in root.

---
