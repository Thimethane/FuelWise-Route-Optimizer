# Quick Start Guide - For Evaluators

**Time to setup:** 3 minutes  
**Time to test:** 2 minutes  
**Total:** 5 minutes to see it working

---

## Step 1: Extract and Setup (3 minutes)

```bash
# Extract the archive
tar -xzf fuel_route_optimizer.tar.gz
cd fuel_route_optimizer

# Install dependencies
pip install -r requirements.txt

# Initialize database
python manage.py migrate

# Import fuel station data
python manage.py import_fuel_data fuel_prices.csv

# Output:
# Cleared existing fuel stations
# Importing fuel stations from fuel_prices.csv
# Successfully imported 8152 fuel stations

# Start the server
python manage.py runserver
```

---

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

## What to Look For

### ✅ Performance
- Response time: <1 second
- External API calls: 1 (ideal requirement)
- Computation time: <0.5s

### ✅ Quality
- Complete error handling
- Proper validation messages
- Clean JSON responses

### ✅ Optimization
- Fuel stops 300-450 miles apart
- Competitive pricing selected
- Total cost reasonable

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

## Documentation

- **README.md** - Complete documentation
- **TECHNICAL_DEEPDIVE.md** - Architecture details
- **DEPLOYMENT.md** - Setup instructions
- **EXECUTIVE_SUMMARY.md** - Key achievements
- **LOOM_SCRIPT.md** - Video demonstration guide

---

## Troubleshooting

**"Server won't start"**
```bash
# Make sure port 8000 is free
lsof -ti:8000 | xargs kill -9
python manage.py runserver
```

**"No fuel stations found"**
```bash
# Re-import data
python manage.py import_fuel_data fuel_prices.csv
```

**"Slow responses"**
```bash
# First request is always slower (no cache)
# Run the same route twice to see caching in action
```

---

## Contact

**Timothee Ringuyeneza**  
📧 timotheeringuyeneza@gmail.com

Questions? I'm available to:
- Walk through the code
- Explain architectural decisions
- Discuss optimizations
- Answer any questions

---

**⏱️ Total Time to See Working: ~5 minutes**

This quick start demonstrates:
- Easy setup
- Fast performance
- Production quality
- Clean architecture
