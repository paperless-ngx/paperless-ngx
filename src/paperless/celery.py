import os

from celery import Celery
from celery.signals import worker_process_init
from kombu.serialization import register

from paperless.signed_pickle import signed_pickle_dumps
from paperless.signed_pickle import signed_pickle_loads

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

# ---------------------------------------------------------------------------
# Signed-pickle serializer: pickle with HMAC-SHA256 integrity verification.
#
# Protects against malicious pickle injection via an exposed Redis broker.
# Messages are signed on the producer side and verified before deserialization
# on the worker side using Django's SECRET_KEY.
# ---------------------------------------------------------------------------

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
