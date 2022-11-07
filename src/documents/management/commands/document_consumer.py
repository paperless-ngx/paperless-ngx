import logging
import os
from pathlib import Path
from pathlib import PurePath
from threading import Event
from threading import Thread
from time import monotonic
from time import sleep
from typing import Final

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from documents.models import Tag
from documents.parsers import is_file_ext_supported
from documents.tasks import consume_file
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

try:
    from inotifyrecursive import INotify, flags
except ImportError:
    INotify = flags = None

logger = logging.getLogger("paperless.management.consumer")


def _tags_from_path(filepath):
    """Walk up the directory tree from filepath to CONSUMPTION_DIR
    and get or create Tag IDs for every directory.
    """
    normalized_consumption_dir = os.path.abspath(
        os.path.normpath(settings.CONSUMPTION_DIR),
    )
    tag_ids = set()
    path_parts = Path(filepath).relative_to(normalized_consumption_dir).parent.parts
    for part in path_parts:
        tag_ids.add(
            Tag.objects.get_or_create(name__iexact=part, defaults={"name": part})[0].pk,
        )

    return tag_ids


def _is_ignored(filepath: str) -> bool:
    normalized_consumption_dir = os.path.abspath(
        os.path.normpath(settings.CONSUMPTION_DIR),
    )
    filepath_relative = PurePath(filepath).relative_to(normalized_consumption_dir)
    return any(filepath_relative.match(p) for p in settings.CONSUMER_IGNORE_PATTERNS)


def _consume(filepath):
    if os.path.isdir(filepath) or _is_ignored(filepath):
        return

    if not os.path.isfile(filepath):
        logger.debug(f"Not consuming file {filepath}: File has moved.")
        return

    if not is_file_ext_supported(os.path.splitext(filepath)[1]):
        logger.warning(f"Not consuming file {filepath}: Unknown file extension.")
        return

    # Total wait time: up to 500ms
    os_error_retry_count: Final[int] = 50
    os_error_retry_wait: Final[float] = 0.01

    read_try_count = 0
    file_open_ok = False
    os_error_str = None

    while (read_try_count < os_error_retry_count) and not file_open_ok:
        try:
            with open(filepath, "rb"):
                file_open_ok = True
        except OSError as e:
            read_try_count += 1
            os_error_str = str(e)
            sleep(os_error_retry_wait)

    if read_try_count >= os_error_retry_count:
        logger.warning(f"Not consuming file {filepath}: OS reports {os_error_str}")
        return

    tag_ids = None
    try:
        if settings.CONSUMER_SUBDIRS_AS_TAGS:
            tag_ids = _tags_from_path(filepath)
    except Exception:
        logger.exception("Error creating tags from path")

    try:
        logger.info(f"Adding {filepath} to the task queue.")
        consume_file.delay(
            filepath,
            override_tag_ids=list(tag_ids) if tag_ids else None,
        )
    except Exception:
        # Catch all so that the consumer won't crash.
        # This is also what the test case is listening for to check for
        # errors.
        logger.exception("Error while consuming document")


def _consume_wait_unmodified(file):
    if _is_ignored(file):
        return

    logger.debug(f"Waiting for file {file} to remain unmodified")
    mtime = -1
    size = -1
    current_try = 0
    while current_try < settings.CONSUMER_POLLING_RETRY_COUNT:
        try:
            stat_data = os.stat(file)
            new_mtime = stat_data.st_mtime
            new_size = stat_data.st_size
        except FileNotFoundError:
            logger.debug(
                f"File {file} moved while waiting for it to remain " f"unmodified.",
            )
            return
        if new_mtime == mtime and new_size == size:
            _consume(file)
            return
        mtime = new_mtime
        size = new_size
        sleep(settings.CONSUMER_POLLING_DELAY)
        current_try += 1

    logger.error(f"Timeout while waiting on file {file} to remain unmodified.")


class Handler(FileSystemEventHandler):
    def on_created(self, event):
        Thread(target=_consume_wait_unmodified, args=(event.src_path,)).start()

    def on_moved(self, event):
        Thread(target=_consume_wait_unmodified, args=(event.dest_path,)).start()


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory.
    """

    # This is here primarily for the tests and is irrelevant in production.
    stop_flag = Event()
    # Also only for testing, configures in one place the timeout used before checking
    # the stop flag
    testing_timeout_s: Final[float] = 0.5
    testing_timeout_ms: Final[float] = testing_timeout_s * 1000.0

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            default=settings.CONSUMPTION_DIR,
            nargs="?",
            help="The consumption directory.",
        )
        parser.add_argument("--oneshot", action="store_true", help="Run only once.")

        # Only use during unit testing, will configure a timeout
        # Leaving it unset or false and the consumer will exit when it
        # receives SIGINT
        parser.add_argument(
            "--testing",
            action="store_true",
            help="Flag used only for unit testing",
            default=False,
        )

    def handle(self, *args, **options):
        directory = options["directory"]
        recursive = settings.CONSUMER_RECURSIVE

        if not directory:
            raise CommandError("CONSUMPTION_DIR does not appear to be set.")

        directory = os.path.abspath(directory)

        if not os.path.isdir(directory):
            raise CommandError(f"Consumption directory {directory} does not exist")

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
            self.handle_inotify(directory, recursive, options["testing"])
        else:
            self.handle_polling(directory, recursive, options["testing"])

        logger.debug("Consumer exiting.")

    def handle_polling(self, directory, recursive, is_testing: bool):
        logger.info(f"Polling directory for changes: {directory}")

        timeout = None
        if is_testing:
            timeout = self.testing_timeout_s
            logger.debug(f"Configuring timeout to {timeout}s")

        observer = PollingObserver(timeout=settings.CONSUMER_POLLING)
        observer.schedule(Handler(), directory, recursive=recursive)
        observer.start()
        try:
            while observer.is_alive():
                observer.join(timeout)
                if self.stop_flag.is_set():
                    observer.stop()
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    def handle_inotify(self, directory, recursive, is_testing: bool):
        logger.info(f"Using inotify to watch directory for changes: {directory}")

        timeout = None
        if is_testing:
            timeout = self.testing_timeout_ms
            logger.debug(f"Configuring timeout to {timeout}ms")

        inotify = INotify()
        inotify_flags = flags.CLOSE_WRITE | flags.MOVED_TO
        if recursive:
            descriptor = inotify.add_watch_recursive(directory, inotify_flags)
        else:
            descriptor = inotify.add_watch(directory, inotify_flags)

        inotify_debounce: Final[float] = settings.CONSUMER_INOTIFY_DELAY

        finished = False

        notified_files = {}

        while not finished:
            try:
                for event in inotify.read(timeout=timeout):
                    if recursive:
                        path = inotify.get_path(event.wd)
                    else:
                        path = directory
                    filepath = os.path.join(path, event.name)
                    notified_files[filepath] = monotonic()

                # Check the files against the timeout
                still_waiting = {}
                for filepath in notified_files:
                    # Time of the last inotify event for this file
                    last_event_time = notified_files[filepath]

                    # Current time - last time over the configured timeout
                    waited_long_enough = (
                        monotonic() - last_event_time
                    ) > inotify_debounce

                    # Also make sure the file exists still, some scanners might write a
                    # temporary file first
                    file_still_exists = os.path.exists(filepath) and os.path.isfile(
                        filepath,
                    )

                    if waited_long_enough and file_still_exists:
                        _consume(filepath)
                    elif file_still_exists:
                        still_waiting[filepath] = last_event_time

                # These files are still waiting to hit the timeout
                notified_files = still_waiting

                # If files are waiting, need to exit read() to check them
                # Otherwise, go back to infinite sleep time, but only if not testing
                if len(notified_files) > 0:
                    timeout = inotify_debounce
                elif is_testing:
                    timeout = self.testing_timeout_ms
                else:
                    timeout = None

                if self.stop_flag.is_set():
                    logger.debug("Finishing because event is set")
                    finished = True

            except KeyboardInterrupt:
                logger.info("Received SIGINT, stopping inotify")
                finished = True

        inotify.rm_watch(descriptor)
        inotify.close()
