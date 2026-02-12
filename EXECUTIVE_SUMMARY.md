This updated version of your **README.md** preserves your entire original structure and content while seamlessly integrating the `make` commands to provide an even more professional "Quick Start" experience.

---

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

## 🛠️ Manual Installation & Environment

### 1. Installation

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

The import command uses an **UPSERT strategy**.

| Mode | Provider | Estimated Time | Description |
| --- | --- | --- | --- |
| **Mock** | Deterministic Alg | **< 30 seconds** | Uses state-aware clustering for local development. |
| **Pro** | **Google Maps** | **~10-15 minutes** | High-speed, high-accuracy production geocoding. |
| **Free** | Nominatim (OSM) | **~2 hours** | Respects 1-req/sec rate limits. |

**Commands:**

```bash
# 1. Fast Demo (Import + State-Aware Mock Coordinates)
python manage.py import_fuel_data fuel_prices.csv --use-mock

# 2. Production Import (Uses GOOGLE_MAPS_API_KEY from .env)
python manage.py import_fuel_data fuel_prices.csv --geocode

```

---

## 🐳 Docker Deployment & DB Init

### 1. Infrastructure Setup

```bash
docker-compose up -d

```

### 2. Manual Container Initialization

```bash
# Run migrations inside the container
docker-compose exec web python manage.py makemigrations routing
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# Seed the Data
docker-compose exec web python manage.py import_fuel_data fuel_prices.csv --geocode

```

---

## 🖥️ Interactive Demo

The project includes a CLI-based demo suite to showcase the API's logic, speed, and accuracy.

```bash
# Run via Docker (Recommended)
docker-compose exec web python demo.py

# Run Locally
python demo.py

```

### What the demo tests:

* **Health Check**: Validates DB connectivity and station count.
* **Multi-Route Optimization**: Benchmarks Short (SF ➔ LA), Medium (CHI ➔ HOU), and Long (NY ➔ LA) trips.
* **Performance Grading**: Automatically grades the API response time.

---

## 📚 API Documentation

### `POST /api/optimize-route/`

**Payload:**

```json
{
  "start": "Chicago, IL",
  "finish": "Miami, FL"
}

```

**Key Response Fields:**

* `total_fuel_cost`: Total estimated expenditure.
* `fuel_stops`: Array of stations including `distance_from_start`.
* `map_api_calls`: Demonstrates caching efficiency.

---

## 🛠️ Architecture & Performance

### Caching Strategy

1. **Level 1 (Redis/LocMem)**: Stores full route objects and geocoding results (TTL: 1hr - 24hr).
2. **Level 2 (Database)**: Lat/Lng coordinates are persisted to avoid redundant API hits.
3. **Level 3 (Mock Fallback)**: Ensures high availability even if external Map APIs are down.

---

## 📞 Support & Links

* **Engineer**: Timothee Ringuyeneza
* **Email**: [timotheeringuyeneza@gmail.com](mailto:timotheeringuyeneza@gmail.com)
* **Postman Collection**: `Fuel_Route_Optimizer.postman_collection.json` included in root.

---

**Would you like me to create a quick "How to Run" video script or GIF description for your GitHub profile to showcase the `make setup` process?**