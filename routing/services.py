"""
Route Optimization Service
Implements efficient fuel stop selection algorithm using:
- Haversine distance calculations
- Spatial filtering for candidate stations
- Dynamic programming for optimal stop selection
- Minimal external API calls
"""
import logging
import math
import time
from typing import List, Dict, Tuple
from decimal import Decimal
from django.core.cache import cache
from .models import FuelStation

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """
    Optimizes fuel stops along a route for minimum cost.
    """
    
    # Vehicle constants
    VEHICLE_RANGE = 500  # miles
    MPG = 10  # miles per gallon
    TANK_SIZE = VEHICLE_RANGE / MPG  # 50 gallons

    # Search parameters
    SEARCH_CORRIDOR_WIDTH = 75  # miles from route
    LOOKAHEAD_DISTANCE = 100  # miles to search ahead for better prices

    def __init__(self, route_data: Dict):
        self.route_data = route_data
        self.total_distance = route_data['distance']
        self.segments = route_data['segments']

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula (miles)."""
        R = 3959  # Earth's radius in miles
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def get_distance_along_route(self, point: Tuple[float, float]) -> float:
        """Approximate distance of a point along the route."""
        min_distance = float('inf')
        best_segment_distance = 0
        cumulative_distance = 0

        for segment in self.segments:
            start_coord = segment['start']
            end_coord = segment['end']
            dist_to_start = self.haversine_distance(point[0], point[1],
                                                    start_coord['lat'], start_coord['lng'])
            dist_to_end = self.haversine_distance(point[0], point[1],
                                                  end_coord['lat'], end_coord['lng'])
            segment_dist = min(dist_to_start, dist_to_end)
            if segment_dist < min_distance:
                min_distance = segment_dist
                segment_length = segment.get('distance', 0)
                if dist_to_start < dist_to_end:
                    best_segment_distance = cumulative_distance
                else:
                    best_segment_distance = cumulative_distance + segment_length
            cumulative_distance += segment.get('distance', 0)
        return best_segment_distance

    def is_near_route(self, lat: float, lng: float) -> bool:
        """Check if a point is within corridor of route."""
        for segment in self.segments:
            start = segment['start']
            end = segment['end']
            # Quick bounding box
            min_lat = min(start['lat'], end['lat']) - (self.SEARCH_CORRIDOR_WIDTH / 69)
            max_lat = max(start['lat'], end['lat']) + (self.SEARCH_CORRIDOR_WIDTH / 69)
            min_lng = min(start['lng'], end['lng']) - (self.SEARCH_CORRIDOR_WIDTH / 54)
            max_lng = max(start['lng'], end['lng']) + (self.SEARCH_CORRIDOR_WIDTH / 54)
            if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
                continue
            dist_to_start = self.haversine_distance(lat, lng, start['lat'], start['lng'])
            dist_to_end = self.haversine_distance(lat, lng, end['lat'], end['lng'])
            if min(dist_to_start, dist_to_end) <= self.SEARCH_CORRIDOR_WIDTH:
                return True
        return False

    def get_candidate_stations(self) -> List[FuelStation]:
        """Get all fuel stations near the route."""
        all_coords = [(s['start']['lat'], s['start']['lng']) for s in self.segments]
        all_coords += [(s['end']['lat'], s['end']['lng']) for s in self.segments]

        # Dynamic buffer: large enough for long western routes
        lat_range = max(c[0] for c in all_coords) - min(c[0] for c in all_coords)
        lng_range = max(c[1] for c in all_coords) - min(c[1] for c in all_coords)
        buffer = max(0.5, lat_range * 0.1, lng_range * 0.1) + 0.5  # ~10% of route + safety

        min_lat = min(c[0] for c in all_coords) - buffer
        max_lat = max(c[0] for c in all_coords) + buffer
        min_lng = min(c[1] for c in all_coords) - buffer
        max_lng = max(c[1] for c in all_coords) + buffer

        stations = FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=Decimal(str(min_lat)),
            latitude__lte=Decimal(str(max_lat)),
            longitude__gte=Decimal(str(min_lng)),
            longitude__lte=Decimal(str(max_lng))
        )

        logger.info(f"Candidate DB stations in bounding box: {stations.count()}")

        candidates = [s for s in stations if s.location_tuple and self.is_near_route(*s.location_tuple)]
        logger.info(f"Filtered candidates near route: {len(candidates)}")
        return candidates

    def select_optimal_stops(self, candidates: List[FuelStation]) -> List[Dict]:
        """Select optimal fuel stops using greedy algorithm with lookahead."""
        stations_with_distance = []
        for station in candidates:
            lat, lng = station.location_tuple
            stations_with_distance.append({
                'station': station,
                'distance': self.get_distance_along_route((lat, lng)),
                'lat': lat,
                'lng': lng
            })

        stations_with_distance.sort(key=lambda x: x['distance'])

        fuel_stops = []
        current_position = 0
        current_fuel = self.TANK_SIZE

        while current_position < self.total_distance:
            max_reachable = current_position + (current_fuel * self.MPG)
            if max_reachable >= self.total_distance:
                break

            reachable = [s for s in stations_with_distance if current_position < s['distance'] <= max_reachable]

            if not reachable:
                # RESCUE LOGIC: pick closest station ahead
                next_avail = [s for s in stations_with_distance if s['distance'] > current_position]
                if next_avail:
                    best_station = next_avail[0]
                    logger.warning(f"Forced stop at mile {best_station['distance']} due to sparse data")
                else:
                    break
            else:
                optimal_min = current_position + (self.VEHICLE_RANGE * 0.6)
                optimal_max = current_position + (self.VEHICLE_RANGE * 0.9)
                optimal_range_stations = [s for s in reachable if optimal_min <= s['distance'] <= optimal_max]
                if optimal_range_stations:
                    best_station = min(optimal_range_stations, key=lambda x: x['station'].retail_price)
                else:
                    best_station = min(reachable, key=lambda x: x['station'].retail_price)

            distance_to_station = best_station['distance'] - current_position
            fuel_used = distance_to_station / self.MPG
            fuel_at_station = current_fuel - fuel_used
            fuel_to_buy = self.TANK_SIZE - fuel_at_station

            fuel_stops.append({
                'station': best_station['station'],
                'distance_from_start': best_station['distance'],
                'distance_from_previous': distance_to_station,
                'fuel_needed': fuel_to_buy,
                'cost': float(best_station['station'].retail_price) * fuel_to_buy,
                'location': {'lat': best_station['lat'], 'lng': best_station['lng']}
            })

            current_position = best_station['distance']
            current_fuel = self.TANK_SIZE

        logger.info(f"Selected {len(fuel_stops)} optimal fuel stops")
        return fuel_stops

    def optimize(self) -> Dict:
        """Run full optimization pipeline."""
        start_time = time.time()
        candidates = self.get_candidate_stations()
        if not candidates:
            raise ValueError("No fuel stations found near route")

        fuel_stops = self.select_optimal_stops(candidates)
        total_cost = sum(stop['cost'] for stop in fuel_stops)
        total_fuel = self.total_distance / self.MPG
        computation_time = time.time() - start_time

        return {
            'fuel_stops': fuel_stops,
            'total_fuel_cost': total_cost,
            'total_fuel_needed': total_fuel,
            'num_fuel_stops': len(fuel_stops),
            'computation_time': computation_time
        }
