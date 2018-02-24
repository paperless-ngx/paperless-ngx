import datetime
import logging
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...consumer import Consumer, ConsumerError
from ...mail import MailFetcher, MailFetcherError


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory, and fetch any mail available.
    """

    ORIGINAL_DOCS = os.path.join(settings.MEDIA_ROOT, "documents", "originals")
    THUMB_DOCS = os.path.join(settings.MEDIA_ROOT, "documents", "thumbnails")

    def __init__(self, *args, **kwargs):

        self.verbosity = 0

        self.file_consumer = None
        self.mail_fetcher = None
        self.first_iteration = True

        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("directory", default=settings.CONSUMPTION_DIR, nargs='?')
        parser.add_argument("--loop-time", default=settings.CONSUMER_LOOP_TIME, type=int)
        parser.add_argument("--mail-delta", default=10, type=int)
        parser.add_argument("--oneshot", action='store_true')

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]
        directory = options['directory']
        loop_time = options['loop_time']
        mail_delta = datetime.timedelta(minutes=options['mail_delta'])

        try:
            self.file_consumer = Consumer(consume=directory)
            self.mail_fetcher = MailFetcher(consume=directory)
        except (ConsumerError, MailFetcherError) as e:
            raise CommandError(e)

        for path in (self.ORIGINAL_DOCS, self.THUMB_DOCS):
            try:
                os.makedirs(path)
            except FileExistsError:
                pass

        logging.getLogger(__name__).info(
            "Starting document consumer at {}".format(directory)
        )

        if options['oneshot']:
            self.loop(mail_delta=mail_delta)
        else:
            try:
                while True:
                    self.loop(mail_delta=mail_delta)
                    time.sleep(loop_time)
                    if self.verbosity > 1:
                        print(".", int(time.time()))
            except KeyboardInterrupt:
                print("Exiting")

    def loop(self, mail_delta):

        # Occasionally fetch mail and store it to be consumed on the next loop
        # We fetch email when we first start up so that it is not necessary to
        # wait for 10 minutes after making changes to the config file.
        delta = self.mail_fetcher.last_checked + mail_delta
        if self.first_iteration or delta < datetime.datetime.now():
            self.first_iteration = False
            self.mail_fetcher.pull()

        # Consume whatever files we can
        self.file_consumer.run()
