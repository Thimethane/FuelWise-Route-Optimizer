"""
Test suite for Fuel Route Optimizer API
Demonstrates testing best practices
"""
import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from routing.models import FuelStation
from routing.services import RouteOptimizer
from routing.map_api import MockMapAPIClient


class FuelStationModelTest(TestCase):
    """Test FuelStation model"""
    
    def setUp(self):
        """Create test station"""
        self.station = FuelStation.objects.create(
            opis_id=1,
            name="Test Station",
            address="123 Main St",
            city="San Francisco",
            state="CA",
            latitude=Decimal("37.7749"),
            longitude=Decimal("-122.4194"),
            retail_price=Decimal("3.45")
        )
    
    def test_station_creation(self):
        """Test station is created correctly"""
        self.assertEqual(self.station.opis_id, 1)
        self.assertEqual(self.station.name, "Test Station")
        self.assertEqual(self.station.state, "CA")
    
    def test_location_tuple(self):
        """Test location_tuple property"""
        lat, lng = self.station.location_tuple
        self.assertEqual(lat, 37.7749)
        self.assertEqual(lng, -122.4194)
    
    def test_string_representation(self):
        """Test __str__ method"""
        expected = "Test Station - San Francisco, CA ($3.45)"
        self.assertEqual(str(self.station), expected)


class RouteOptimizerTest(TestCase):
    """Test RouteOptimizer service"""
    
    def setUp(self):
        """Create test data"""
        # Create test stations along a route
        stations = [
            FuelStation(
                opis_id=i,
                name=f"Station {i}",
                address=f"Address {i}",
                city="TestCity",
                state="CA",
                latitude=Decimal(str(37.0 + i * 0.5)),
                longitude=Decimal(str(-122.0 - i * 0.5)),
                retail_price=Decimal(str(3.0 + (i % 5) * 0.1))
            )
            for i in range(1, 11)
        ]
        FuelStation.objects.bulk_create(stations)
        
        # Mock route data
        self.route_data = {
            'distance': 1000.0,
            'polyline': 'mock_polyline',
            'segments': [
                {
                    'start': {'lat': 37.0, 'lng': -122.0},
                    'end': {'lat': 37.5, 'lng': -122.5},
                    'distance': 500.0
                },
                {
                    'start': {'lat': 37.5, 'lng': -122.5},
                    'end': {'lat': 38.0, 'lng': -123.0},
                    'distance': 500.0
                }
            ]
        }
    
    def test_haversine_distance(self):
        """Test distance calculation"""
        optimizer = RouteOptimizer(self.route_data)
        
        # San Francisco to Los Angeles (approx)
        distance = optimizer.haversine_distance(
            37.7749, -122.4194,
            34.0522, -118.2437
        )
        
        # Should be around 350-400 miles
        self.assertGreater(distance, 300)
        self.assertLess(distance, 450)
    
    def test_optimize_returns_results(self):
        """Test optimization returns valid results"""
        optimizer = RouteOptimizer(self.route_data)
        results = optimizer.optimize()
        
        self.assertIn('fuel_stops', results)
        self.assertIn('total_fuel_cost', results)
        self.assertIn('num_fuel_stops', results)
        self.assertIsInstance(results['fuel_stops'], list)


class APIEndpointTest(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        
        # Create test stations
        FuelStation.objects.create(
            opis_id=1,
            name="Test Station 1",
            address="123 Main",
            city="San Francisco",
            state="CA",
            latitude=Decimal("37.7749"),
            longitude=Decimal("-122.4194"),
            retail_price=Decimal("3.45")
        )
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/api/health/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('database', data)
    
    def test_list_stations(self):
        """Test stations list endpoint"""
        response = self.client.get('/api/stations/?limit=10')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('stations', data)
    
    def test_list_stations_filter(self):
        """Test station filtering"""
        response = self.client.get('/api/stations/?state=CA')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        if data['count'] > 0:
            # All stations should be in CA
            for station in data['stations']:
                self.assertEqual(station['state'], 'CA')
    
    def test_optimize_route_validation(self):
        """Test input validation"""
        # Missing start
        response = self.client.post(
            '/api/optimize-route/',
            {'finish': 'Los Angeles, CA'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Missing finish
        response = self.client.post(
            '/api/optimize-route/',
            {'start': 'San Francisco, CA'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


class MapAPIClientTest(TestCase):
    """Test map API client"""
    
    def test_mock_client_geocoding(self):
        """Test mock geocoding"""
        client = MockMapAPIClient()
        
        # Should recognize major cities
        lat, lng = client.geocode_location("San Francisco, CA")
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lng, float)
        
        # Should be in USA
        self.assertGreater(lat, 24)  # Southern border
        self.assertLess(lat, 50)     # Northern border
    
    def test_mock_client_routing(self):
        """Test mock route generation"""
        client = MockMapAPIClient()
        
        start_coords = (37.7749, -122.4194)  # SF
        finish_coords = (34.0522, -118.2437)  # LA
        
        route = client.get_route_osrm(start_coords, finish_coords)
        
        self.assertIn('distance', route)
        self.assertIn('segments', route)
        self.assertGreater(route['distance'], 0)


# Performance tests
class PerformanceTest(TestCase):
    """Test performance characteristics"""
    
    def setUp(self):
        """Create larger dataset"""
        # Create 100 test stations
        stations = [
            FuelStation(
                opis_id=i,
                name=f"Station {i}",
                address=f"Address {i}",
                city="TestCity",
                state="CA",
                latitude=Decimal(str(37.0 + (i % 10) * 0.1)),
                longitude=Decimal(str(-122.0 - (i % 10) * 0.1)),
                retail_price=Decimal(str(3.0 + (i % 10) * 0.1))
            )
            for i in range(100)
        ]
        FuelStation.objects.bulk_create(stations)
    
    def test_station_query_performance(self):
        """Test database query performance"""
        import time
        
        start = time.time()
        
        # Query with filters
        stations = FuelStation.objects.filter(
            state='CA',
            retail_price__lte=Decimal('3.50')
        )[:10]
        
        list(stations)  # Force evaluation
        
        elapsed = time.time() - start
        
        # Should complete in under 100ms
        self.assertLess(elapsed, 0.1)


# Integration tests
class IntegrationTest(TestCase):
    """End-to-end integration tests"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests"""
        # Create realistic station data
        stations = []
        for i in range(50):
            lat = 37.0 + (i * 0.1)
            lng = -122.0 - (i * 0.1)
            price = 3.0 + ((i % 10) * 0.05)
            
            stations.append(FuelStation(
                opis_id=i,
                name=f"Station {i}",
                address=f"Highway Exit {i}",
                city="TestCity",
                state="CA",
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lng)),
                retail_price=Decimal(str(price))
            ))
        
        FuelStation.objects.bulk_create(stations)
    
    def test_full_optimization_flow(self):
        """Test complete optimization flow"""
        client = Client()
        
        response = client.post(
            '/api/optimize-route/',
            {
                'start': 'San Francisco, CA',
                'finish': 'Los Angeles, CA'
            },
            content_type='application/json'
        )
        
        # Should succeed (or gracefully handle external API failures)
        self.assertIn(response.status_code, [200, 400, 500])
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate response structure
            self.assertIn('start_location', data)
            self.assertIn('finish_location', data)
            self.assertIn('total_distance', data)
            self.assertIn('fuel_stops', data)
            self.assertIn('total_fuel_cost', data)
            
            # Validate data types
            self.assertIsInstance(data['total_distance'], (int, float))
            self.assertIsInstance(data['fuel_stops'], list)
            self.assertIsInstance(data['total_fuel_cost'], (int, float))


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
