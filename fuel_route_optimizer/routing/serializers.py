"""
DRF Serializers for route optimization API.
Implements clean API contracts with proper validation.
"""
from rest_framework import serializers
from .models import FuelStation


class FuelStationSerializer(serializers.ModelSerializer):
    """
    Serializer for fuel station data.

    Note:
        The issue is that `ModelSerializer` automatically adds a
        UniqueValidator to fields like `opis_id`. When validating
        output data, Django thinks you are trying to create new
        stations and complains if those IDs already exist.

        To fix this, we override `opis_id` to remove the "unique" check.
    """

    # Override to remove automatic UniqueValidator
    opis_id = serializers.IntegerField()

    class Meta:
        model = FuelStation
        fields = ['opis_id', 'name', 'address', 'city', 'state',
                  'latitude', 'longitude', 'retail_price']


class OptimalFuelStopSerializer(serializers.Serializer):
    """Serializer for a recommended fuel stop along the route."""

    station = FuelStationSerializer()
    distance_from_start = serializers.FloatField(help_text="Miles from start")
    distance_from_previous = serializers.FloatField(help_text="Miles from previous stop")
    fuel_needed = serializers.FloatField(help_text="Gallons to refuel")
    cost = serializers.FloatField(help_text="Cost to refuel at this station")

    # Route segment info
    segment_index = serializers.IntegerField(help_text="Route segment this stop is on")
    location_on_route = serializers.DictField(help_text="Lat/lng on route")


class RouteInputSerializer(serializers.Serializer):
    """Validates input for route optimization request."""

    start = serializers.CharField(
        max_length=255,
        help_text="Start location (city, state or address in USA)"
    )
    finish = serializers.CharField(
        max_length=255,
        help_text="Finish location (city, state or address in USA)"
    )

    def validate(self, data):
        """Ensure start and finish are different."""
        if data['start'].strip().lower() == data['finish'].strip().lower():
            raise serializers.ValidationError(
                "Start and finish locations must be different"
            )
        return data


class RouteResponseSerializer(serializers.Serializer):
    """Complete route optimization response."""

    # Route metadata
    start_location = serializers.DictField(help_text="Start coordinates and address")
    finish_location = serializers.DictField(help_text="Finish coordinates and address")
    total_distance = serializers.FloatField(help_text="Total route distance in miles")
    total_fuel_needed = serializers.FloatField(help_text="Total gallons needed (10 MPG)")

    # Fuel stops
    fuel_stops = OptimalFuelStopSerializer(many=True)
    total_fuel_cost = serializers.FloatField(help_text="Total money spent on fuel")
    num_fuel_stops = serializers.IntegerField(help_text="Number of fuel stops")

    # Route polyline for map display
    route_polyline = serializers.CharField(
        help_text="Encoded polyline for map rendering"
    )

    # Performance metrics
    computation_time = serializers.FloatField(help_text="API computation time in seconds")
    map_api_calls = serializers.IntegerField(help_text="Number of external API calls made")
