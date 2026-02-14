"""
DRF Views for Route Optimization API.
Implements clean REST endpoints with hybrid map support and comprehensive error handling.
"""
import logging
import time
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache

from .serializers import (
    RouteInputSerializer,
    RouteResponseSerializer,
    FuelStationSerializer
)
from .map_api import MapAPIClient  # Updated: Hybrid client only
from .services import RouteOptimizer
from .models import FuelStation

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
def optimize_route(request):
    """
    POST /api/optimize-route/

    Optimize fuel stops along a route between two US locations.
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
        # Hybrid Map Client
        # Handles Google -> Nominatim -> Mock fallback internally
        map_client = MapAPIClient(use_cache=True, use_mock=False)

        # Step 1: Calculate route
        route_data = map_client.get_route(start, finish)

        logger.info(
            f"Route calculated: {route_data['distance']:.1f} miles, "
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

        # Optional: Validate response schema (safe for production)
        response_serializer = RouteResponseSerializer(data=response_data)
        if not response_serializer.is_valid():
            logger.error(f"Response validation failed: {response_serializer.errors}")

        logger.info(
            f"Optimization complete: "
            f"{optimization_result['num_fuel_stops']} stops, "
            f"${optimization_result['total_fuel_cost']:.2f}, "
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
    Health check endpoint.
    """
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM fuel_stations")
            station_count = cursor.fetchone()[0]

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
            'version': '2.0.0'  # bumped version
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
    List fuel stations with optional filters.
    """
    queryset = FuelStation.objects.all()

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

    limit = min(int(request.query_params.get('limit', 100)), 500)
    queryset = queryset[:limit]

    serializer = FuelStationSerializer(queryset, many=True)

    return Response({
        'count': len(serializer.data),
        'stations': serializer.data
    })
