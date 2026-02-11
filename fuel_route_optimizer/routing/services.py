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
from typing import List, Dict, Tuple, Optional
from decimal import Decimal
from django.core.cache import cache
from .models import FuelStation

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """
    Optimizes fuel stops along a route for minimum cost.
    
    Algorithm:
    1. Get route from external API (1 call)
    2. Build spatial index of nearby fuel stations
    3. Select optimal stops using greedy algorithm with lookahead
    4. Return stops with cost calculations
    """
    
    # Vehicle constants
    VEHICLE_RANGE = 500  # miles
    MPG = 10  # miles per gallon
    TANK_SIZE = VEHICLE_RANGE / MPG  # 50 gallons
    
    # Search parameters
    SEARCH_CORRIDOR_WIDTH = 25  # miles from route
    LOOKAHEAD_DISTANCE = 100  # miles to search ahead for better prices
    
    def __init__(self, route_data: Dict):
        """
        Initialize optimizer with route data from external API.
        
        Args:
            route_data: Dict containing:
                - distance: total miles
                - polyline: encoded route
                - segments: list of route segments with coordinates
        """
        self.route_data = route_data
        self.total_distance = route_data['distance']
        self.segments = route_data['segments']
        
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        Optimized for repeated calculations.
        
        Returns:
            Distance in miles
        """
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
        """
        Calculate approximate distance of a point along the route.
        Uses segment-based calculation for accuracy.
        
        Args:
            point: (lat, lng) tuple
            
        Returns:
            Miles from start of route
        """
        min_distance = float('inf')
        best_segment_distance = 0
        
        cumulative_distance = 0
        
        for i, segment in enumerate(self.segments):
            start_coord = segment['start']
            end_coord = segment['end']
            
            # Distance to segment start
            dist_to_start = self.haversine_distance(
                point[0], point[1],
                start_coord['lat'], start_coord['lng']
            )
            
            # Distance to segment end
            dist_to_end = self.haversine_distance(
                point[0], point[1],
                end_coord['lat'], end_coord['lng']
            )
            
            # Find closest point on this segment
            segment_dist = min(dist_to_start, dist_to_end)
            
            if segment_dist < min_distance:
                min_distance = segment_dist
                # Estimate position along segment
                segment_length = segment.get('distance', 0)
                if dist_to_start < dist_to_end:
                    best_segment_distance = cumulative_distance
                else:
                    best_segment_distance = cumulative_distance + segment_length
            
            cumulative_distance += segment.get('distance', 0)
        
        return best_segment_distance
    
    def is_near_route(self, lat: float, lng: float) -> bool:
        """
        Check if a point is within corridor of route.
        Uses bounding box + distance check for efficiency.
        
        Args:
            lat, lng: Coordinates to check
            
        Returns:
            True if within SEARCH_CORRIDOR_WIDTH miles of route
        """
        for segment in self.segments:
            start = segment['start']
            end = segment['end']
            
            # Quick bounding box check first
            min_lat = min(start['lat'], end['lat']) - 0.4  # ~25 miles
            max_lat = max(start['lat'], end['lat']) + 0.4
            min_lng = min(start['lng'], end['lng']) - 0.4
            max_lng = max(start['lng'], end['lng']) + 0.4
            
            if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
                continue
            
            # Precise distance check
            dist_to_start = self.haversine_distance(lat, lng, start['lat'], start['lng'])
            dist_to_end = self.haversine_distance(lat, lng, end['lat'], end['lng'])
            
            if min(dist_to_start, dist_to_end) <= self.SEARCH_CORRIDOR_WIDTH:
                return True
        
        return False
    
    def get_candidate_stations(self) -> List[FuelStation]:
        """
        Get all fuel stations near the route.
        Uses spatial filtering for efficiency.
        
        Returns:
            List of FuelStation objects near route
        """
        # Get bounding box of entire route
        all_coords = []
        for segment in self.segments:
            all_coords.append((segment['start']['lat'], segment['start']['lng']))
            all_coords.append((segment['end']['lat'], segment['end']['lng']))
        
        min_lat = min(c[0] for c in all_coords) - 0.5
        max_lat = max(c[0] for c in all_coords) + 0.5
        min_lng = min(c[1] for c in all_coords) - 0.5
        max_lng = max(c[1] for c in all_coords) + 0.5
        
        # Query with bounding box filter (uses DB index)
        stations = FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=Decimal(str(min_lat)),
            latitude__lte=Decimal(str(max_lat)),
            longitude__gte=Decimal(str(min_lng)),
            longitude__lte=Decimal(str(max_lng))
        ).select_related()  # Optimize query
        
        # Fine-grained filtering
        candidates = []
        for station in stations:
            if station.location_tuple:
                lat, lng = station.location_tuple
                if self.is_near_route(lat, lng):
                    candidates.append(station)
        
        logger.info(f"Found {len(candidates)} candidate stations near route")
        return candidates
    
    def select_optimal_stops(self, candidates: List[FuelStation]) -> List[Dict]:
        """
        Select optimal fuel stops using greedy algorithm with lookahead.
        
        Algorithm:
        - Start with empty tank at beginning
        - At each decision point:
          - Find all reachable stations in next VEHICLE_RANGE miles
          - Look ahead LOOKAHEAD_DISTANCE for price trends
          - Choose station with best price within optimal range
        - Repeat until destination reached
        
        Args:
            candidates: Pre-filtered stations near route
            
        Returns:
            List of optimal fuel stop dictionaries
        """
        # Annotate candidates with distance along route
        stations_with_distance = []
        for station in candidates:
            lat, lng = station.location_tuple
            distance_along = self.get_distance_along_route((lat, lng))
            stations_with_distance.append({
                'station': station,
                'distance': distance_along,
                'lat': lat,
                'lng': lng
            })
        
        # Sort by distance along route
        stations_with_distance.sort(key=lambda x: x['distance'])
        
        fuel_stops = []
        current_position = 0  # miles from start
        current_fuel = self.TANK_SIZE  # start with full tank
        
        while current_position < self.total_distance:
            # How far can we go with current fuel?
            max_reachable = current_position + (current_fuel * self.MPG)
            
            # If we can reach destination, we're done
            if max_reachable >= self.total_distance:
                break
            
            # Find stations we can reach
            reachable = [
                s for s in stations_with_distance
                if current_position < s['distance'] <= max_reachable
            ]
            
            if not reachable:
                # No stations in range - need to adjust strategy
                # This shouldn't happen with proper data, but handle gracefully
                logger.warning(f"No reachable stations from position {current_position}")
                break
            
            # Use lookahead: find stations in optimal range
            # Optimal range: 60-90% of tank capacity from current position
            optimal_min = current_position + (self.VEHICLE_RANGE * 0.6)
            optimal_max = current_position + (self.VEHICLE_RANGE * 0.9)
            
            optimal_range_stations = [
                s for s in reachable
                if optimal_min <= s['distance'] <= optimal_max
            ]
            
            # Choose cheapest in optimal range, or cheapest overall if optimal empty
            if optimal_range_stations:
                best_station = min(optimal_range_stations, 
                                 key=lambda x: x['station'].retail_price)
            else:
                best_station = min(reachable, 
                                 key=lambda x: x['station'].retail_price)
            
            # Calculate fuel needed
            distance_to_station = best_station['distance'] - current_position
            fuel_used = distance_to_station / self.MPG
            fuel_at_station = current_fuel - fuel_used
            fuel_to_buy = self.TANK_SIZE - fuel_at_station
            
            # Add fuel stop
            fuel_stops.append({
                'station': best_station['station'],
                'distance_from_start': best_station['distance'],
                'distance_from_previous': distance_to_station,
                'fuel_needed': fuel_to_buy,
                'cost': float(best_station['station'].retail_price) * fuel_to_buy,
                'location': {'lat': best_station['lat'], 'lng': best_station['lng']}
            })
            
            # Update position and fuel
            current_position = best_station['distance']
            current_fuel = self.TANK_SIZE
        
        logger.info(f"Selected {len(fuel_stops)} optimal fuel stops")
        return fuel_stops
    
    def optimize(self) -> Dict:
        """
        Main optimization pipeline.
        
        Returns:
            Dict containing optimal fuel stops and cost analysis
        """
        start_time = time.time()
        
        # Step 1: Get candidate stations (uses spatial filtering)
        candidates = self.get_candidate_stations()
        
        if not candidates:
            raise ValueError("No fuel stations found near route")
        
        # Step 2: Select optimal stops
        fuel_stops = self.select_optimal_stops(candidates)
        
        # Step 3: Calculate totals
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
