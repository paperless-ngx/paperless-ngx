import hmac
import os
import pickle
from hashlib import sha256

from celery import Celery
from celery.signals import worker_process_init
from kombu.serialization import register

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

# ---------------------------------------------------------------------------
# Signed-pickle serializer: pickle with HMAC-SHA256 integrity verification.
#
# Protects against malicious pickle injection via an exposed Redis broker.
# Messages are signed on the producer side and verified before deserialization
# on the worker side using Django's SECRET_KEY.
# ---------------------------------------------------------------------------

HMAC_SIZE = 32  # SHA-256 digest length


def _get_signing_key() -> bytes:
    from django.conf import settings

    return settings.SECRET_KEY.encode()


def signed_pickle_dumps(obj: object) -> bytes:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    signature = hmac.new(_get_signing_key(), data, sha256).digest()
    return signature + data


def signed_pickle_loads(payload: bytes) -> object:
    if len(payload) < HMAC_SIZE:
        msg = "Signed-pickle payload too short"
        raise ValueError(msg)
    signature = payload[:HMAC_SIZE]
    data = payload[HMAC_SIZE:]
    expected = hmac.new(_get_signing_key(), data, sha256).digest()
    if not hmac.compare_digest(signature, expected):
        msg = "Signed-pickle HMAC verification failed — message may have been tampered with"
        raise ValueError(msg)
    return pickle.loads(data)


register(
    "signed-pickle",
    signed_pickle_dumps,
    signed_pickle_loads,
    content_type="application/x-signed-pickle",
    content_encoding="binary",
)

app = Celery("paperless")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:  # pragma: no cover
    """
    Register built-in parsers eagerly in each Celery worker process.

    This registers only the built-in parsers (no entrypoint discovery) so
    that workers can begin consuming documents immediately.  Entrypoint
    discovery for third-party parsers is deferred to the first call of
    get_parser_registry() inside a task, keeping worker_process_init
    well within its 4-second timeout budget.
    """
    from paperless.parsers.registry import init_builtin_parsers

    init_builtin_parsers()
