import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from documents.consumer import Consumer

try:
    from inotify_simple import INotify, flags
except ImportError:
    INotify = flags = None


class Handler(FileSystemEventHandler):

    def __init__(self, consumer):
        self.consumer = consumer

    def _consume(self, file):
        if os.path.isfile(file):
            try:
                self.consumer.try_consume_file(file)
            except Exception as e:
                logging.getLogger(__name__).error("Error while consuming document: {}".format(e))

    def on_created(self, event):
        self._consume(event.src_path)

    def on_modified(self, event):
        self._consume(event.src_path)

    def on_moved(self, event):
        self._consume(event.src_path)


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory, and fetch any mail available.
    """

    def __init__(self, *args, **kwargs):

        self.verbosity = 0
        self.logger = logging.getLogger(__name__)

        self.file_consumer = None
        self.mail_fetcher = None
        self.first_iteration = True

        self.consumer = Consumer()

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

        for d in (settings.ORIGINALS_DIR, settings.THUMBNAIL_DIR):
            os.makedirs(d, exist_ok=True)

        logging.getLogger(__name__).info(
            "Starting document consumer at {}".format(
                directory
            )
        )

        # Consume all files as this is not done initially by the watchdog
        for entry in os.scandir(directory):
            if entry.is_file():
                self.consumer.try_consume_file(entry.path)

        # Start the watchdog. Woof!
        observer = Observer()
        event_handler = Handler(self.consumer)
        observer.schedule(event_handler, directory, recursive=True)
        observer.start()
        try:
            while observer.is_alive():
                observer.join(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
