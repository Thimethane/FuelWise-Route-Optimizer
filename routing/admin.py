"""
Django admin configuration for fuel stations.
"""
from django.contrib import admin
from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin interface for fuel stations."""
    
    list_display = ['name', 'city', 'state', 'retail_price', 'latitude', 'longitude']
    list_filter = ['state', 'city']
    search_fields = ['name', 'city', 'state', 'address']
    ordering = ['retail_price']
    
    fieldsets = (
        ('Station Info', {
            'fields': ('opis_id', 'name', 'address')
        }),
        ('Location', {
            'fields': ('city', 'state', 'latitude', 'longitude')
        }),
        ('Pricing', {
            'fields': ('rack_id', 'retail_price')
        }),
    )
