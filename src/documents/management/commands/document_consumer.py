import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django_q.tasks import async_task
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

try:
    from inotify_simple import INotify, flags
except ImportError:
    INotify = flags = None


class Handler(FileSystemEventHandler):

    def _consume(self, file):
        if os.path.isfile(file):
            try:
                async_task("documents.tasks.consume_file",
                           file,
                           task_name=os.path.basename(file)[:100])
            except Exception as e:
                # Catch all so that the consumer won't crash.
                logging.getLogger(__name__).error(
                    "Error while consuming document: {}".format(e))

    def on_created(self, event):
        self._consume(event.src_path)

    def on_moved(self, event):
        self._consume(event.src_path)


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory.
    """

    def __init__(self, *args, **kwargs):

        self.verbosity = 0
        self.logger = logging.getLogger(__name__)

        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            default=settings.CONSUMPTION_DIR,
            nargs="?",
            help="The consumption directory."
        )

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]
        directory = options["directory"]

        logging.getLogger(__name__).info(
            "Starting document consumer at {}".format(
                directory
            )
        )

        # Consume all files as this is not done initially by the watchdog
        for entry in os.scandir(directory):
            if entry.is_file():
                async_task("documents.tasks.consume_file",
                           entry.path,
                           task_name=os.path.basename(entry.path)[:100])

        # Start the watchdog. Woof!
        if settings.CONSUMER_POLLING > 0:
            logging.getLogger(__name__).info(
                "Using polling instead of file system notifications.")
            observer = PollingObserver(timeout=settings.CONSUMER_POLLING)
        else:
            observer = Observer()
        event_handler = Handler()
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
        try:
            while observer.is_alive():
                observer.join(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
