#!/usr/bin/env python
"""
Demo script for Fuel Route Optimizer API
Showcases key features and performance
"""
import requests
import json
import time
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


class FuelOptimizerDemo:
    """Demo class for testing API"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    def test_health(self):
        """Test health check endpoint"""
        print_header("HEALTH CHECK")
        
        try:
            response = requests.get(f"{self.base_url}/api/health/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print_success("API is healthy")
                print_info(f"Database: {data['database']['fuel_stations']} stations")
                print_info(f"Cache: {'Connected' if data['cache']['connected'] else 'Disconnected'}")
                print_info(f"Version: {data['version']}")
                return True
            else:
                print_error(f"Health check failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Cannot connect to API: {e}")
            print_warning("Make sure server is running: python manage.py runserver")
            return False
    
    def test_route(self, start, finish, name=""):
        """Test route optimization"""
        if name:
            print_header(f"TEST: {name}")
        else:
            print_header(f"ROUTE: {start} → {finish}")
        
        payload = {
            "start": start,
            "finish": finish
        }
        
        print_info(f"Request: {start} → {finish}")
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/optimize-route/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            request_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Print results
                print_success(f"Route optimized successfully")
                print()
                print(f"  📍 Start: {data['start_location']['address']}")
                print(f"  📍 Finish: {data['finish_location']['address']}")
                print(f"  📏 Distance: {data['total_distance']:.1f} miles")
                print(f"  ⛽ Fuel Needed: {data['total_fuel_needed']:.1f} gallons")
                print(f"  🛑 Fuel Stops: {data['num_fuel_stops']}")
                print(f"  💰 Total Cost: ${data['total_fuel_cost']:.2f}")
                print(f"  🔌 API Calls: {data['map_api_calls']}")
                print(f"  ⚡ Computation: {data['computation_time']:.3f}s")
                print(f"  🌐 Request Time: {request_time:.3f}s")
                
                # Show fuel stops
                if data['fuel_stops']:
                    print(f"\n  {Colors.BOLD}Fuel Stops:{Colors.ENDC}")
                    for i, stop in enumerate(data['fuel_stops'], 1):
                        station = stop['station']
                        print(f"    {i}. {station['name']}")
                        print(f"       📍 {station['city']}, {station['state']}")
                        print(f"       📏 {stop['distance_from_start']:.1f} mi from start")
                        print(f"       ⛽ {stop['fuel_needed']:.1f} gal @ ${station['retail_price']:.3f}/gal")
                        print(f"       💰 ${stop['cost']:.2f}")
                        print()
                
                # Store result
                self.results.append({
                    'name': name,
                    'distance': data['total_distance'],
                    'stops': data['num_fuel_stops'],
                    'cost': data['total_fuel_cost'],
                    'time': request_time
                })
                
                return True
                
            else:
                error_data = response.json()
                print_error(f"Request failed: {response.status_code}")
                print_warning(f"Error: {error_data.get('error', 'Unknown error')}")
                if 'details' in error_data:
                    print_warning(f"Details: {error_data['details']}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Request error: {e}")
            return False
    
    def test_stations(self):
        """Test stations endpoint"""
        print_header("LIST STATIONS")
        
        try:
            # Test basic list
            response = requests.get(
                f"{self.base_url}/api/stations/?limit=5",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Found {data['count']} stations")
                
                if data['stations']:
                    print(f"\n  {Colors.BOLD}Sample Stations:{Colors.ENDC}")
                    for station in data['stations'][:5]:
                        print(f"    • {station['name']}")
                        print(f"      {station['city']}, {station['state']} - ${station['retail_price']:.3f}/gal")
                
                # Test filtering
                print_info("\nTesting filters...")
                
                response = requests.get(
                    f"{self.base_url}/api/stations/?state=CA&max_price=3.50&limit=3",
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    print_success(f"Filter test: Found {data['count']} CA stations under $3.50")
                
                return True
            else:
                print_error(f"Request failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Request error: {e}")
            return False
    
    def run_full_demo(self):
        """Run complete demonstration"""
        print_header("FUEL ROUTE OPTIMIZER - DEMO")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Base URL: {self.base_url}")
        
        # Health check
        if not self.test_health():
            return
        
        input("\nPress Enter to continue...")
        
        # Test stations
        self.test_stations()
        
        input("\nPress Enter to test routes...")
        
        # Test various routes
        routes = [
            {
                'start': 'San Francisco, CA',
                'finish': 'Los Angeles, CA',
                'name': 'Short Route (380 miles)'
            },
            {
                'start': 'Chicago, IL',
                'finish': 'Houston, TX',
                'name': 'Medium Route (1,100 miles)'
            },
            {
                'start': 'New York, NY',
                'finish': 'Los Angeles, CA',
                'name': 'Long Route (2,800 miles)'
            },
        ]
        
        for route in routes:
            self.test_route(route['start'], route['finish'], route['name'])
            input("\nPress Enter for next test...")
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print performance summary"""
        print_header("PERFORMANCE SUMMARY")
        
        if not self.results:
            print_warning("No results to summarize")
            return
        
        print(f"  {Colors.BOLD}Test Results:{Colors.ENDC}\n")
        print(f"  {'Route':<30} {'Distance':<12} {'Stops':<8} {'Cost':<12} {'Time':<10}")
        print(f"  {'-'*70}")
        
        for result in self.results:
            print(f"  {result['name']:<30} "
                  f"{result['distance']:>8.1f} mi  "
                  f"{result['stops']:>4}    "
                  f"${result['cost']:>8.2f}  "
                  f"{result['time']:>7.3f}s")
        
        # Averages
        avg_time = sum(r['time'] for r in self.results) / len(self.results)
        total_cost = sum(r['cost'] for r in self.results)
        
        print(f"  {'-'*70}")
        print(f"\n  Average Response Time: {avg_time:.3f}s")
        print(f"  Total Fuel Cost (all routes): ${total_cost:.2f}")
        
        # Performance grade
        if avg_time < 0.5:
            grade = "EXCELLENT ⭐⭐⭐"
        elif avg_time < 1.0:
            grade = "GOOD ⭐⭐"
        else:
            grade = "ACCEPTABLE ⭐"
        
        print(f"\n  Performance Grade: {Colors.OKGREEN}{grade}{Colors.ENDC}")


def main():
    """Main entry point"""
    demo = FuelOptimizerDemo()
    demo.run_full_demo()


if __name__ == "__main__":
    main()
