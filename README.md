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

---

### 1. Mannual Installation & Environment

```bash
# Clone and enter
git clone https://github.com/Thimethane/FuelWise-Route-Optimizer
cd FuelWise-Route-Optimizer

# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure secrets
cp .env.example .env  # Update with your GOOGLE_MAPS_API_KEY

```

### 2. Database Initialization

```bash
# Run migrations
python manage.py makemigrations routing
python manage.py makemigrations
python manage.py migrate
```

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

**Cleanup Command:**

```bash
# Via Make
make clean-db

# Via Docker
docker-compose exec web python manage.py shell -c "from routing.models import FuelStation; FuelStation.objects.all().delete()"

# Via Local Python
python manage.py shell -c "from routing.models import FuelStation; FuelStation.objects.all().delete()"

```

---

### ⚙️ Update the `Makefile`

To make this effortless, add this `clean-db` target to the `Makefile`:

```makefile
.PHONY: clean-db
clean-db:
	$(PYTHON) manage.py shell -c "from routing.models import FuelStation; FuelStation.objects.all().delete()"
	@echo "✅ Database cleared. You can now run a fresh import."

```

---

### 🧠 Why the Mock data might not return "correct" data:

When you run the **Chicago ➔ Houston** route, the algorithm looks for stations within a specific "Search Corridor" (e.g., 75 miles from the road).

1. **Mathematical Mismatch:** If the Mock algorithm assigns a station in "Tillatoba, MS" a random coordinate that is actually 200 miles away from the highway, the spatial query `latitude BETWEEN ... AND ...` will skip it.
2. **State Logic:** If your mock generator assigns coordinates based on a simple bounding box, it might place a "Texas" station inside "Oklahoma," causing the `state='TX'` filter to return no results for that specific location.


**Commands:**

```bash
# 1. Fast Demo (Import + State-Aware Mock Coordinates)
python manage.py import_fuel_data fuel_prices.csv --use-mock

# 2. Production Import (Uses GOOGLE_MAPS_API_KEY from .env)
python manage.py import_fuel_data fuel_prices.csv --geocode

# 3. Standard Refresh (Price update only, keeps existing coords)
python manage.py import_fuel_data fuel_prices.csv

```

### 4. Run & Test

```bash
python manage.py runserver

# In a new terminal:
curl -X POST http://localhost:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "San Francisco, CA", "finish": "New York, NY"}'

```
---

## 🖥️ Interactive Demo

The project includes a CLI-based demo suite to showcase the API's logic, speed, and accuracy across different route lengths.

```bash
# 1. Ensure the server is running
python manage.py runserver

# 2. In a new terminal, run the demo
python demo.py

```

### What the demo tests:

* **Health Check**: Validates DB connectivity and station count.
* **Station Filtering**: Tests `GET` filtering by state and max price.
* **Multi-Route Optimization**: Runs benchmarks for Short (SF ➔ LA), Medium (CHI ➔ HOU), and Long (NY ➔ LA) trips.
* **Performance Grading**: Automatically grades the API response time.

---

To ensure your project is production-ready with the specific settings and initialization steps you provided, I have aligned the **Docker** configuration and **README** instructions to work seamlessly with your `settings.py` logic.

### 1. The `.env.example` File

This matches your `settings.py` environment-based switching logic.

```env
# --- Security ---
DEBUG=True
SECRET_KEY=generate-a-secure-key-for-production
ALLOWED_HOSTS=localhost,127.0.0.1,web
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# --- Database ---
# Set to 'postgres' to use the Docker container, 'sqlite' for local
DB_ENGINE=postgres
DB_NAME=fuel_db
DB_USER=fuel_user
DB_PASSWORD=fuel_pass
DB_HOST=db
DB_PORT=5432

# --- Cache ---
# Used by django-redis
REDIS_URL=redis://redis:6379/0

# --- External APIs ---
GOOGLE_MAPS_API_KEY=your_google_api_key_here

```

---

### 2. The `docker-compose.yml`

This sets up the **PostgreSQL** container, the **Redis** container, and the **Django** app, ensuring they connect using the names defined in your `DB_HOST`.

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: fuel_optimizer_db
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_DB=fuel_db
      - POSTGRES_USER=fuel_user
      - POSTGRES_PASSWORD=fuel_pass
    ports:
      - "5433:5432" # Host 5433 maps to Container 5432 to avoid local conflicts
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fuel_user -d fuel_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: fuel_optimizer_redis
    expose:
      - 6379

  web:
    build: .
    container_name: fuel_optimizer_web
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DB_HOST=db # Maps to the 'db' service name above
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

volumes:
  postgres_data:

```

---

#### 🚀 Docker Deployment & DB Init

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

**Key Response Fields:**

* `total_fuel_cost`: Total estimated expenditure.
* `fuel_stops`: Array of stations including `distance_from_start` and `step_cost`.
* `route_polyline`: Encoded string for map visualization.
* `map_api_calls`: Demonstrates caching efficiency (0 on repeat trips).

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

## 📞 Support & Links

* **Engineer**: Timothee Ringuyeneza
* **Email**: [timotheeringuyeneza@gmail.com](mailto:timotheeringuyeneza@gmail.com)
* **Postman Collection**: `Fuel_Route_Optimizer.postman_collection.json` included in root.

---
