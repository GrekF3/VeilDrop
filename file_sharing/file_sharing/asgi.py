from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import os
from django.urls import path
from anon_support_manager.consumers import SupportConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'file_sharing.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path('ws/support/<str:ticket_id>/', SupportConsumer.as_asgi()),
        ])
    ),
})