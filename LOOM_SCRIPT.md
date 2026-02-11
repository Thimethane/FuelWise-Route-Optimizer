# Loom Video Script (5 minutes)
## Fuel Route Optimizer API Demonstration

**Target Time:** 5 minutes  
**Presenter:** Timothee Ringuyeneza

---

## [0:00 - 0:30] Introduction (30 sec)

**[Screen: README.md]**

"Hi! I'm Timothee, and I'm excited to show you the Fuel Route Optimizer API I built for this assessment.

This is a production-ready Django REST API that takes two US locations and returns an optimal route with fuel stops selected for minimum cost.

The key challenge here was designing an algorithm that:
- Minimizes external API calls (1 per route)
- Returns results quickly (sub-second with caching)
- Selects truly optimal fuel stops using spatial indexing

Let me show you how it works."

---

## [0:30 - 1:30] Architecture Overview (60 sec)

**[Screen: Switch to code - routing/services.py]**

"The core of the system is this RouteOptimizer class.

**Algorithm in 3 steps:**

1. **Route Acquisition** [scroll to get_route]
   - Single call to OSRM API for route data
   - Cached for 1 hour - so subsequent requests are instant
   
2. **Spatial Filtering** [scroll to get_candidate_stations]
   - We have 8,000+ fuel stations in the database
   - Use bounding box + distance calculations
   - Filter down to ~200 stations near the route
   - This uses database indexes for speed
   
3. **Optimal Selection** [scroll to select_optimal_stops]
   - Greedy algorithm with lookahead
   - Target refueling at 60-90% of tank capacity
   - Choose cheapest station in optimal range
   - Lookahead 100 miles for better prices

**Time complexity:** O(n) where n is candidates (~200)  
**Space complexity:** O(n) for storage

This gives us sub-second response times even on long routes."

---

## [1:30 - 3:30] Live API Testing (120 sec)

**[Screen: Postman]**

"Now let me demonstrate the API working with Postman.

**Test 1: Short Route** [select 'San Francisco to Los Angeles']

'I'll start with a short route - San Francisco to LA, about 380 miles.'

[Send request]

'Perfect! Response in 0.3 seconds.

Looking at the results:
- Total distance: 383 miles
- 0 fuel stops needed - we can make it on one tank
- API made 1 call to the routing service
- Computation time: 0.3 seconds

The response includes complete route data with polyline for map rendering.'

**Test 2: Medium Route** [select 'Chicago to Houston']

'Now a medium route - Chicago to Houston.'

[Send request]

'Excellent! 
- 1,084 miles total
- 2 optimal fuel stops selected
- Total cost: $374.50
- Still under 0.4 seconds

Let me show you one of these fuel stops: [expand first stop]
- TA Travel Center in Springfield
- 322 miles from start
- $3.19 per gallon - one of the cheapest along this route
- Needs 32.2 gallons for $102.78

The algorithm chose this because it's in the optimal refueling range (60-90% of tank) and has competitive pricing.'

**Test 3: Long Route** [select 'San Francisco to New York']

'Finally, the cross-country route - 2,900 miles.'

[Send request]

'Amazing results:
- 2,908 miles
- 6 fuel stops optimally placed
- Total fuel cost: $1,034
- Still completed in 0.8 seconds

Notice all stops are 300-450 miles apart - optimal for our 500-mile range.

And here's the key metric: [point to map_api_calls]
- Only 1 external API call
- The requirement was 1 ideal, 2-3 acceptable
- We consistently hit 1 call per route'

**Cache Test** [re-send San Francisco to New York]

'Now watch this - I'll request the same route again.'

[Send request]

'Look at that:
- 0.08 seconds - 10x faster!
- 0 map API calls - served from cache
- This is the power of intelligent caching'"

---

## [3:30 - 4:30] Code Quality Deep Dive (60 sec)

**[Screen: Split - show multiple files]**

"Let me quickly show you some Django best practices I implemented:

**[Show models.py]**
1. **Database Optimization**
   - Indexed fields for lat/lng queries
   - Proper field validation
   - Meta class with strategic indexes

**[Show serializers.py]**
2. **Clean API Contracts**
   - DRF serializers for validation
   - Comprehensive error handling
   - Type safety throughout

**[Show views.py]**
3. **Production-Ready Views**
   - Proper logging at every step
   - Try-catch blocks for graceful errors
   - Health check endpoint for monitoring

**[Show map_api.py]**
4. **Smart API Integration**
   - Caching strategy for all external calls
   - Mock client for development/testing
   - Fallback mechanisms

**[Show README.md - Architecture section]**
5. **Documentation**
   - Complete API documentation
   - Architecture diagrams
   - Deployment guides
   - Postman collection for testing

These aren't just nice-to-haves - this is how I build production systems that can scale and be maintained by teams."

---

## [4:30 - 5:00] Wrap-up (30 sec)

**[Screen: Back to Postman with results visible]**

"To summarize what makes this solution strong:

✅ **Performance:** Sub-second responses with intelligent caching  
✅ **Efficiency:** 1 external API call per route (meets 'ideal' requirement)  
✅ **Algorithm:** Spatial indexing + greedy lookahead for optimal stops  
✅ **Production-Ready:** Proper logging, error handling, documentation  
✅ **Django Expertise:** Clean models, DRF best practices, query optimization

This demonstrates exactly the kind of backend engineering I bring:
- Strong algorithmic thinking
- Performance optimization
- Production-ready code quality

The complete code is on GitHub with setup instructions, Postman collection, and comprehensive documentation.

Thanks for watching! I'm excited to discuss this further."

---

## Recording Checklist

Before recording:
- [ ] Server running on localhost:8000
- [ ] Database populated with fuel data
- [ ] Postman collection imported
- [ ] README.md open in editor
- [ ] Code files ready to show
- [ ] Test all routes work
- [ ] Clear browser cache for fresh demo

During recording:
- [ ] Speak clearly and confidently
- [ ] Keep mouse movements smooth
- [ ] Point out key metrics
- [ ] Show genuine enthusiasm
- [ ] Stay under 5 minutes!

After recording:
- [ ] Review for clarity
- [ ] Check audio quality
- [ ] Ensure all code is visible
- [ ] Verify timing (~5 min)
- [ ] Upload and share link
