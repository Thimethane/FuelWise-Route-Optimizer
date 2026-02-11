"""
URL configuration for routing app.
"""
from django.urls import path
from . import views

app_name = 'routing'

urlpatterns = [
    # Main optimization endpoint
    path('optimize-route/', views.optimize_route, name='optimize-route'),
    
    # Utility endpoints
    path('health/', views.health_check, name='health'),
    path('stations/', views.list_stations, name='list-stations'),
]
