import os

from django.core.asgi import get_asgi_application

# Fetch Django ASGI application early to ensure AppRegistry is populated
# before importing consumers and AuthMiddlewareStack that may import ORM
# models.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter  # noqa: E402
from channels.routing import URLRouter  # noqa: E402

from paperless.urls import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    },
)
