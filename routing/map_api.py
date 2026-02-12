"""
Map API Integration - Hybrid Robust Version

Geocoding Priority:
1. Google Geocoding API (if key provided)
2. Nominatim (OpenStreetMap)
3. Deterministic Mock fallback

Routing:
- OSRM (free, open source)

This version preserves:
- Cache logic
- OSRM routing
- Existing route structure
- Mock fallback behavior
"""

import logging
import requests
import hashlib
import time
from typing import Dict, Tuple, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MapAPIClient:

    OSRM_BASE_URL = "https://router.project-osrm.org"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    USER_AGENT = "FuelRouteOptimizer/1.0"

    def __init__(self, use_cache=True, use_mock=False):
        self.use_cache = use_cache
        self.use_mock = use_mock
        self.api_calls_made = 0

    # =====================================================
    # GEOCODING ENTRY POINT
    # =====================================================

    def geocode_location(self, location: str) -> Tuple[float, float]:
        cache_key = f"geocode:{hashlib.md5(location.encode()).hexdigest()}"

        if self.use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Geocode cache hit for {location}")
                return cached

        if self.use_mock:
            result = self._get_mock_coords(location)
            logger.info(f"MOCK Geocoded {location}")
        else:
            result = self._live_geocode(location)

        if self.use_cache and result:
            cache.set(cache_key, result, timeout=86400)

        return result

    # =====================================================
    # LIVE GEOCODING STRATEGY
    # =====================================================

    def _live_geocode(self, location: str) -> Tuple[float, float]:
        google_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)

        if google_key:
            try:
                coords = self._call_google(location, google_key)
                if coords:
                    logger.info(f"Google geocoded {location}")
                    return coords
            except Exception as e:
                logger.warning(f"Google geocode failed: {e}")

        try:
            coords = self._call_nominatim(location)
            if coords:
                logger.info(f"Nominatim geocoded {location}")
                time.sleep(1.1)  # Respect rate limit
                return coords
        except Exception as e:
            logger.warning(f"Nominatim failed: {e}")

        logger.warning(f"Falling back to MOCK for {location}")
        return self._get_mock_coords(location)

    # =====================================================
    # GOOGLE GEOCODING
    # =====================================================

    def _call_google(self, location: str, api_key: str) -> Optional[Tuple[float, float]]:
        params = {
            "address": location,
            "key": api_key,
            "region": "us"
        }
        response = requests.get(self.GOOGLE_GEOCODE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            self.api_calls_made += 1
            return (loc["lat"], loc["lng"])
        return None

    # =====================================================
    # NOMINATIM GEOCODING
    # =====================================================

    def _call_nominatim(self, location: str) -> Optional[Tuple[float, float]]:
        params = {
            'q': location,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'us'
        }
        headers = {'User-Agent': self.USER_AGENT}
        response = requests.get(self.NOMINATIM_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            self.api_calls_made += 1
            return (float(data[0]['lat']), float(data[0]['lon']))
        return None

    # =====================================================
    # MOCK FALLBACK (STATE-AWARE)
    # =====================================================

    def _get_mock_coords(self, location: str) -> Tuple[float, float]:
        # Extract state from "City, ST"
        parts = location.split(',')
        state = parts[-1].strip()[:2].upper() if len(parts) > 1 else "US"

        # Approximate center of US states used in routes
        centers = {
            "CA": (36.7, -119.4), "NV": (38.8, -116.4), "UT": (39.3, -111.0),
            "WY": (42.7, -107.3), "NE": (41.1, -98.2), "IA": (41.8, -93.2),
            "IL": (40.6, -89.3), "OH": (40.4, -82.9), "PA": (41.2, -77.1),
            "NY": (40.7, -74.0), "NJ": (40.0, -74.4)
        }

        base_lat, base_lng = centers.get(state, (39.8, -98.5))  # Default to US center

        # Add deterministic jitter so stations aren't exactly on top of each other
        h = int(hashlib.md5(location.encode()).hexdigest(), 16)
        lat = base_lat + ((h % 400) - 200) / 100.0
        lng = base_lng + (((h >> 8) % 400) - 200) / 100.0

        return (lat, lng)

    # =====================================================
    # ROUTING (UNCHANGED - OSRM)
    # =====================================================

    def get_route_osrm(self, start_coords: Tuple[float, float],
                       finish_coords: Tuple[float, float]) -> Dict:

        start_lng, start_lat = start_coords[1], start_coords[0]
        finish_lng, finish_lat = finish_coords[1], finish_coords[0]

        url = f"{self.OSRM_BASE_URL}/route/v1/driving/{start_lng},{start_lat};{finish_lng},{finish_lat}"
        params = {'overview': 'full', 'geometries': 'geojson', 'steps': 'true'}

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data['code'] != 'Ok':
            raise ValueError("OSRM routing failed")

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

        polyline = str(coordinates)
        self.api_calls_made += 1

        return {
            'distance': distance_miles,
            'polyline': polyline,
            'segments': segments,
            'provider': 'OSRM'
        }

    # =====================================================
    # MAIN ROUTE ENTRY (UNCHANGED STRUCTURE)
    # =====================================================

    def get_route(self, start: str, finish: str) -> Dict:

        cache_key = hashlib.md5(f"route:{start}:{finish}".encode()).hexdigest()

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
