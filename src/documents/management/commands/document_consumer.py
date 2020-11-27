import logging
import os
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_q.tasks import async_task
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

try:
    from inotify_simple import INotify, flags
except ImportError:
    INotify = flags = None

logger = logging.getLogger(__name__)


def _consume(file):
    try:
        if os.path.isfile(file):
            async_task("documents.tasks.consume_file",
                       file,
                       task_name=os.path.basename(file)[:100])
        else:
            logger.debug(
                f"Not consuming file {file}: File has moved.")

    except Exception as e:
        # Catch all so that the consumer won't crash.
        # This is also what the test case is listening for to check for
        # errors.
        logger.error(
            "Error while consuming document: {}".format(e))


def _consume_wait_unmodified(file, num_tries=20, wait_time=1):
    mtime = -1
    current_try = 0
    while current_try < num_tries:
        try:
            new_mtime = os.stat(file).st_mtime
        except FileNotFoundError:
            logger.debug(f"File {file} moved while waiting for it to remain "
                         f"unmodified.")
            return
        if new_mtime == mtime:
            _consume(file)
            return
        mtime = new_mtime
        sleep(wait_time)
        current_try += 1

    logger.error(f"Timeout while waiting on file {file} to remain unmodified.")


class Handler(FileSystemEventHandler):

    def on_created(self, event):
        _consume_wait_unmodified(event.src_path)

    def on_moved(self, event):
        _consume_wait_unmodified(event.dest_path)


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory.
    """

    # This is here primarily for the tests and is irrelevant in production.
    stop_flag = False

    def __init__(self, *args, **kwargs):

        self.logger = logging.getLogger(__name__)

        BaseCommand.__init__(self, *args, **kwargs)
        self.observer = None

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            default=settings.CONSUMPTION_DIR,
            nargs="?",
            help="The consumption directory."
        )
        parser.add_argument(
            "--oneshot",
            action="store_true",
            help="Run only once."
        )

    def handle(self, *args, **options):
        directory = options["directory"]

        if not directory:
            raise CommandError(
                "CONSUMPTION_DIR does not appear to be set."
            )

        if not os.path.isdir(directory):
            raise CommandError(
                f"Consumption directory {directory} does not exist")

        for entry in os.scandir(directory):
            _consume(entry.path)

        if options["oneshot"]:
            return

        if settings.CONSUMER_POLLING == 0 and INotify:
            self.handle_inotify(directory)
        else:
            self.handle_polling(directory)

        logger.debug("Consumer exiting.")

    def handle_polling(self, directory):
        logging.getLogger(__name__).info(
            f"Polling directory for changes: {directory}")
        self.observer = PollingObserver(timeout=settings.CONSUMER_POLLING)
        self.observer.schedule(Handler(), directory, recursive=False)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
                if self.stop_flag:
                    self.observer.stop()
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

    def handle_inotify(self, directory):
        logging.getLogger(__name__).info(
            f"Using inotify to watch directory for changes: {directory}")

        inotify = INotify()
        inotify.add_watch(directory, flags.CLOSE_WRITE | flags.MOVED_TO)
        try:
            while not self.stop_flag:
                for event in inotify.read(timeout=1000, read_delay=1000):
                    file = os.path.join(directory, event.name)
                    if os.path.isfile(file):
                        _consume(file)
        except KeyboardInterrupt:
            pass
