import json
import os

from asgiref.sync import async_to_sync
from channels.auth import AuthMiddlewareStack
from channels.generic.websocket import WebsocketConsumer
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')


class StatusConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()
        async_to_sync(self.channel_layer.group_add)('status_updates', self.channel_name)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)('status_updates', self.channel_name)

    def status_update(self, event):
        self.send(json.dumps(event['data']))


websocket_urlpatterns = [
    re_path(r'ws/status/$', StatusConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
