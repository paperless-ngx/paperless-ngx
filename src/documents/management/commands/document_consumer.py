import logging
import os
from pathlib import Path, PurePath
from threading import Thread
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_q.tasks import async_task
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from documents.models import Tag
from documents.parsers import is_file_ext_supported

try:
    from inotifyrecursive import INotify, flags
except ImportError:
    INotify = flags = None

logger = logging.getLogger("paperless.management.consumer")


def _tags_from_path(filepath):
    """Walk up the directory tree from filepath to CONSUMPTION_DIR
       and get or create Tag IDs for every directory.
    """
    tag_ids = set()
    path_parts = Path(filepath).relative_to(
                settings.CONSUMPTION_DIR).parent.parts
    for part in path_parts:
        tag_ids.add(Tag.objects.get_or_create(name__iexact=part, defaults={
            "name": part
        })[0].pk)

    return tag_ids


def _is_ignored(filepath: str) -> bool:
    filepath_relative = PurePath(filepath).relative_to(
        settings.CONSUMPTION_DIR)
    return any(
        filepath_relative.match(p) for p in settings.CONSUMER_IGNORE_PATTERNS)


def _consume(filepath):
    if os.path.isdir(filepath) or _is_ignored(filepath):
        return

    if not os.path.isfile(filepath):
        logger.debug(
            f"Not consuming file {filepath}: File has moved.")
        return

    if not is_file_ext_supported(os.path.splitext(filepath)[1]):
        logger.warning(
            f"Not consuming file {filepath}: Unknown file extension.")
        return

    tag_ids = None
    try:
        if settings.CONSUMER_SUBDIRS_AS_TAGS:
            tag_ids = _tags_from_path(filepath)
    except Exception as e:
        logger.exception("Error creating tags from path")

    try:
        logger.info(f"Adding {filepath} to the task queue.")
        async_task("documents.tasks.consume_file",
                   filepath,
                   override_tag_ids=tag_ids if tag_ids else None,
                   task_name=os.path.basename(filepath)[:100])
    except Exception as e:
        # Catch all so that the consumer won't crash.
        # This is also what the test case is listening for to check for
        # errors.
        logger.exception("Error while consuming document")


def _consume_wait_unmodified(file):
    if _is_ignored(file):
        return

    logger.debug(f"Waiting for file {file} to remain unmodified")
    mtime = -1
    current_try = 0
    while current_try < settings.CONSUMER_POLLING_RETRY_COUNT:
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
        sleep(settings.CONSUMER_POLLING_DELAY)
        current_try += 1

    logger.error(f"Timeout while waiting on file {file} to remain unmodified.")


class Handler(FileSystemEventHandler):

    def on_created(self, event):
        Thread(
            target=_consume_wait_unmodified, args=(event.src_path,)
        ).start()

    def on_moved(self, event):
        Thread(
            target=_consume_wait_unmodified, args=(event.dest_path,)
        ).start()


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory.
    """

    # This is here primarily for the tests and is irrelevant in production.
    stop_flag = False

    observer = None

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
        recursive = settings.CONSUMER_RECURSIVE

        if not directory:
            raise CommandError(
                "CONSUMPTION_DIR does not appear to be set."
            )

        if not os.path.isdir(directory):
            raise CommandError(
                f"Consumption directory {directory} does not exist")

        if recursive:
            for dirpath, _, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    _consume(filepath)
        else:
            for entry in os.scandir(directory):
                _consume(entry.path)

        if options["oneshot"]:
            return

        if settings.CONSUMER_POLLING == 0 and INotify:
            self.handle_inotify(directory, recursive)
        else:
            self.handle_polling(directory, recursive)

        logger.debug("Consumer exiting.")

    def handle_polling(self, directory, recursive):
        logger.info(
            f"Polling directory for changes: {directory}")
        self.observer = PollingObserver(timeout=settings.CONSUMER_POLLING)
        self.observer.schedule(Handler(), directory, recursive=recursive)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)
                if self.stop_flag:
                    self.observer.stop()
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

    def handle_inotify(self, directory, recursive):
        logger.info(
            f"Using inotify to watch directory for changes: {directory}")

        inotify = INotify()
        inotify_flags = flags.CLOSE_WRITE | flags.MOVED_TO
        if recursive:
            descriptor = inotify.add_watch_recursive(directory, inotify_flags)
        else:
            descriptor = inotify.add_watch(directory, inotify_flags)

        try:
            while not self.stop_flag:
                for event in inotify.read(timeout=1000):
                    if recursive:
                        path = inotify.get_path(event.wd)
                    else:
                        path = directory
                    filepath = os.path.join(path, event.name)
                    _consume(filepath)
        except KeyboardInterrupt:
            pass

        inotify.rm_watch(descriptor)
        inotify.close()
