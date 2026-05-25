from django.urls import re_path
from .consumers import ChaseConsumer

websocket_urlpatterns = [
    re_path(r'^ws/chase/$', ChaseConsumer.as_asgi()),
]
