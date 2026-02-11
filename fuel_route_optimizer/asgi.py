"""
ASGI config for fuel_route_optimizer project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fuel_route_optimizer.settings')

application = get_asgi_application()
