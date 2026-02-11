"""
DRF Views for Route Optimization API.
Implements clean REST endpoints with comprehensive error handling.
"""
import logging
import time
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache

from .serializers import (
    RouteInputSerializer,
    RouteResponseSerializer,
    FuelStationSerializer
)
from .map_api import MapAPIClient, MockMapAPIClient
from .services import RouteOptimizer
from .models import FuelStation

logger = logging.getLogger(__name__)


@api_view(['POST'])
def optimize_route(request):
    """
    POST /api/optimize-route/
    
    Optimize fuel stops along a route between two US locations.
    
    Request Body:
        {
            "start": "San Francisco, CA",
            "finish": "New York, NY"
        }
    
    Response:
        {
            "start_location": {"lat": ..., "lng": ..., "address": ...},
            "finish_location": {"lat": ..., "lng": ..., "address": ...},
            "total_distance": 2900.5,
            "total_fuel_needed": 290.05,
            "fuel_stops": [
                {
                    "station": {
                        "opis_id": 123,
                        "name": "Pilot Travel Center",
                        "address": "I-80, Exit 123",
                        "city": "Reno",
                        "state": "NV",
                        "latitude": 39.5296,
                        "longitude": -119.8138,
                        "retail_price": 3.45
                    },
                    "distance_from_start": 220.5,
                    "distance_from_previous": 220.5,
                    "fuel_needed": 22.05,
                    "cost": 76.07,
                    "segment_index": 3,
                    "location_on_route": {"lat": 39.5296, "lng": -119.8138}
                },
                ...
            ],
            "total_fuel_cost": 1034.50,
            "num_fuel_stops": 5,
            "route_polyline": "...",
            "computation_time": 0.342,
            "map_api_calls": 1
        }
    
    Algorithm:
    1. Geocode start/finish (cached)
    2. Get route from OSRM (1 API call, cached)
    3. Filter fuel stations using spatial index
    4. Select optimal stops using greedy + lookahead
    5. Return complete analysis
    
    Performance: Typically <500ms with caching
    """
    start_time = time.time()
    
    # Validate input
    input_serializer = RouteInputSerializer(data=request.data)
    if not input_serializer.is_valid():
        return Response(
            {
                'error': 'Invalid input',
                'details': input_serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    start = input_serializer.validated_data['start']
    finish = input_serializer.validated_data['finish']
    
    logger.info(f"Optimizing route: {start} -> {finish}")
    
    try:
        # Step 1: Get route from map API
        # Use MockMapAPIClient for demo/testing, MapAPIClient for production
        # Toggle based on availability
        try:
            map_client = MapAPIClient(use_cache=True)
            route_data = map_client.get_route(start, finish)
        except Exception as e:
            logger.warning(f"Map API failed, using mock: {e}")
            map_client = MockMapAPIClient(use_cache=True)
            route_data = map_client.get_route(start, finish)
        
        logger.info(
            f"Route calculated: {route_data['distance']:.1f} miles, "
            f"{len(route_data['segments'])} segments, "
            f"{map_client.api_calls_made} API calls"
        )
        
        # Step 2: Optimize fuel stops
        optimizer = RouteOptimizer(route_data)
        optimization_result = optimizer.optimize()
        
        # Step 3: Build response
        response_data = {
            'start_location': route_data['start_location'],
            'finish_location': route_data['finish_location'],
            'total_distance': route_data['distance'],
            'total_fuel_needed': optimization_result['total_fuel_needed'],
            'fuel_stops': _format_fuel_stops(optimization_result['fuel_stops']),
            'total_fuel_cost': round(optimization_result['total_fuel_cost'], 2),
            'num_fuel_stops': optimization_result['num_fuel_stops'],
            'route_polyline': route_data['polyline'],
            'computation_time': round(time.time() - start_time, 3),
            'map_api_calls': map_client.api_calls_made
        }
        
        # Validate response schema
        response_serializer = RouteResponseSerializer(data=response_data)
        if not response_serializer.is_valid():
            logger.error(f"Response validation failed: {response_serializer.errors}")
            # Return anyway for debugging
        
        logger.info(
            f"Optimization complete: {optimization_result['num_fuel_stops']} stops, "
            f"${optimization_result['total_fuel_cost']:.2f} total cost, "
            f"{response_data['computation_time']}s"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return Response(
            {
                'error': 'Invalid request',
                'message': str(e)
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except Exception as e:
        logger.exception(f"Unexpected error optimizing route: {e}")
        return Response(
            {
                'error': 'Server error',
                'message': 'An unexpected error occurred. Please try again.'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _format_fuel_stops(stops: list) -> list:
    """Format fuel stops for API response."""
    formatted = []
    for i, stop in enumerate(stops):
        formatted.append({
            'station': FuelStationSerializer(stop['station']).data,
            'distance_from_start': round(stop['distance_from_start'], 2),
            'distance_from_previous': round(stop['distance_from_previous'], 2),
            'fuel_needed': round(stop['fuel_needed'], 2),
            'cost': round(stop['cost'], 2),
            'segment_index': i,
            'location_on_route': stop['location']
        })
    return formatted


@api_view(['GET'])
def health_check(request):
    """
    GET /api/health/
    
    Health check endpoint for monitoring.
    Returns system status and statistics.
    """
    from django.db import connection
    
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM fuel_stations")
            station_count = cursor.fetchone()[0]
        
        # Check cache
        cache.set('health_check', 'ok', timeout=10)
        cache_ok = cache.get('health_check') == 'ok'
        
        return Response({
            'status': 'healthy',
            'database': {
                'connected': True,
                'fuel_stations': station_count
            },
            'cache': {
                'connected': cache_ok
            },
            'version': '1.0.0'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
def list_stations(request):
    """
    GET /api/stations/
    
    List all fuel stations (paginated).
    Optional filters: state, city, max_price
    
    Query Parameters:
        - state: Filter by state code (e.g., "CA")
        - city: Filter by city name
        - max_price: Maximum price per gallon
        - limit: Results per page (default 100)
    """
    queryset = FuelStation.objects.all()
    
    # Apply filters
    state = request.query_params.get('state')
    if state:
        queryset = queryset.filter(state=state.upper())
    
    city = request.query_params.get('city')
    if city:
        queryset = queryset.filter(city__icontains=city)
    
    max_price = request.query_params.get('max_price')
    if max_price:
        try:
            queryset = queryset.filter(retail_price__lte=float(max_price))
        except ValueError:
            pass
    
    # Pagination
    limit = min(int(request.query_params.get('limit', 100)), 500)
    queryset = queryset[:limit]
    
    serializer = FuelStationSerializer(queryset, many=True)
    
    return Response({
        'count': len(serializer.data),
        'stations': serializer.data
    })
