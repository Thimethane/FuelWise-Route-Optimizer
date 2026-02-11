"""
Map API Integration
Handles routing API calls using OpenRouteService (free, no key needed for basic use)
Alternative: OSRM (Open Source Routing Machine) - completely free, no limits
"""

import logging
import requests
import hashlib
from typing import Dict, Tuple
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MapAPIClient:
    """
    Client for routing APIs.
    Uses OSRM (Open Source Routing Machine) - free and open source.
    Fallback to OpenRouteService if needed.
    """

    OSRM_BASE_URL = "https://router.project-osrm.org"
    ORS_BASE_URL = "https://api.openrouteservice.org"
    ORS_API_KEY = None  # optional API key for higher limits

    def __init__(self, use_cache=True):
        self.use_cache = use_cache
        self.api_calls_made = 0

    def _get_cache_key(self, start: str, finish: str) -> str:
        key_string = f"route:{start}:{finish}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def geocode_location(self, location: str) -> Tuple[float, float]:
        """
        Convert location string to coordinates using Nominatim (free).
        Includes cache for performance.
        """
        cache_key = f"geocode:{hashlib.md5(location.encode()).hexdigest()}"
        if self.use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Geocode cache hit for {location}")
                return cached

        # Use Nominatim API
        url = "https://nominatim.openstreetmap.org/search"
        params = {'q': location, 'format': 'json', 'limit': 1, 'countrycodes': 'us'}
        headers = {'User-Agent': 'FuelRouteOptimizer/1.0'}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                # Retry fallback for messy addresses
                parts = location.split(',')
                if len(parts) >= 3:
                    fallback_query = f"{parts[-3].strip()}, {parts[-2].strip()}, USA"
                    logger.info(f"Retrying geocode with fallback: {fallback_query}")
                    response = requests.get(url, params={'q': fallback_query, **params}, headers=headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    if not data:
                        raise ValueError(f"Location not found: {location}")
                else:
                    raise ValueError(f"Location not found: {location}")

            lat, lng = float(data[0]['lat']), float(data[0]['lon'])
            result = (lat, lng)

            if self.use_cache:
                cache.set(cache_key, result, timeout=86400)

            logger.info(f"Geocoded {location} to {lat}, {lng}")
            return result

        except Exception as e:
            logger.error(f"Geocoding failed for {location}: {e}")
            raise ValueError(f"Could not geocode location: {location}")

    def get_route_osrm(self, start_coords: Tuple[float, float],
                       finish_coords: Tuple[float, float]) -> Dict:
        """Get route from OSRM API."""
        start_lng, start_lat = start_coords[1], start_coords[0]
        finish_lng, finish_lat = finish_coords[1], finish_coords[0]

        url = f"{self.OSRM_BASE_URL}/route/v1/driving/{start_lng},{start_lat};{finish_lng},{finish_lat}"
        params = {'overview': 'full', 'geometries': 'geojson', 'steps': 'true'}

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data['code'] != 'Ok':
                raise ValueError(f"OSRM routing failed: {data.get('message', 'Unknown error')}")

            route = data['routes'][0]
            distance_miles = route['distance'] * 0.000621371
            coordinates = route['geometry']['coordinates']

            segments = []
            steps = route['legs'][0]['steps']
            for step in steps:
                step_coords = step['geometry']['coordinates']
                if len(step_coords) >= 2:
                    start = step_coords[0]
                    end = step_coords[-1]
                    segments.append({
                        'start': {'lat': start[1], 'lng': start[0]},
                        'end': {'lat': end[1], 'lng': end[0]},
                        'distance': step['distance'] * 0.000621371
                    })

            polyline = self._encode_polyline(coordinates)
            self.api_calls_made += 1

            return {'distance': distance_miles, 'polyline': polyline, 'segments': segments, 'provider': 'OSRM'}

        except Exception as e:
            logger.error(f"OSRM routing failed: {e}")
            raise ValueError(f"Route calculation failed: {str(e)}")

    def _encode_polyline(self, coordinates: list) -> str:
        """Simplified polyline encoder (use polyline lib for production)."""
        return str(coordinates)

    def get_route(self, start: str, finish: str) -> Dict:
        """Get route between two locations (main entry)."""
        cache_key = self._get_cache_key(start, finish)
        if self.use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Route cache hit for {start} -> {finish}")
                return cached

        start_coords = self.geocode_location(start)
        finish_coords = self.geocode_location(finish)
        route_data = self.get_route_osrm(start_coords, finish_coords)

        result = {
            'start_location': {'lat': start_coords[0], 'lng': start_coords[1], 'address': start},
            'finish_location': {'lat': finish_coords[0], 'lng': finish_coords[1], 'address': finish},
            'distance': route_data['distance'],
            'polyline': route_data['polyline'],
            'segments': route_data['segments'],
            'map_api_calls': self.api_calls_made
        }

        if self.use_cache:
            cache.set(cache_key, result, timeout=3600)
        return result


# ========================================
# Smart Mock Client
# ========================================

class MockMapAPIClient(MapAPIClient):
    """
    Enhanced Mock Client that scatters stations across the US
    to fix "Single Point" problem and allow routes like SF -> LA.
    """

    def geocode_location(self, location: str) -> Tuple[float, float]:
        """Generate deterministic coordinates across the USA for any location."""
        h = int(hashlib.md5(location.encode()).hexdigest(), 16)
        lat = 25.0 + (h % 2300) / 100.0    # 25.0 -> 48.0
        lng = -120.0 + ((h >> 8) % 4500) / 100.0  # -120.0 -> -75.0
        logger.info(f"MOCK Geocoded {location} to {lat}, {lng}")
        return (lat, lng)

    def get_route_osrm(self, start_coords: Tuple[float, float],
                       finish_coords: Tuple[float, float]) -> Dict:
        """Mock route generation (same as before)."""
        lat1, lng1 = start_coords
        lat2, lng2 = finish_coords

        distance_miles = ((lat2 - lat1)**2 + (lng2 - lng1)**2)**0.5 * 69

        segments = []
        num_segments = 10
        for i in range(num_segments):
            t_start = i / num_segments
            t_end = (i + 1) / num_segments

            seg_start_lat = lat1 + (lat2 - lat1) * t_start
            seg_start_lng = lng1 + (lng2 - lng1) * t_start
            seg_end_lat = lat1 + (lat2 - lat1) * t_end
            seg_end_lng = lng1 + (lng2 - lng1) * t_end

            segments.append({
                'start': {'lat': seg_start_lat, 'lng': seg_start_lng},
                'end': {'lat': seg_end_lat, 'lng': seg_end_lng},
                'distance': distance_miles / num_segments
            })

        self.api_calls_made += 1

        return {
            'distance': distance_miles,
            'polyline': f"MOCK_POLYLINE_{start_coords}_to_{finish_coords}",
            'segments': segments,
            'provider': 'MOCK'
        }
