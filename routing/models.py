"""
Models for fuel station data.
Optimized for fast spatial queries using indexed lat/lng fields.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class FuelStation(models.Model):
    """
    Represents a truck stop with fuel pricing.
    Indexed for efficient geospatial queries.
    """
    opis_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=2, db_index=True)
    
    # Geospatial coordinates - indexed for fast distance calculations
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=6, decimal_places=5)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fuel_stations'
        ordering = ['retail_price']
        indexes = [
            models.Index(fields=['state', 'city']),
            models.Index(fields=['retail_price']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price})"
    
    @property
    def location_tuple(self):
        """Returns (lat, lng) tuple for distance calculations."""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None
