
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sonde.settings')

# Get Django ASGI application
django_asgi_app = get_asgi_application()

# Import routing after Django setup
from chase.routing import websocket_urlpatterns

# Final ASGI Application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})