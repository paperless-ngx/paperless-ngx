import datetime
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

    LOOP_TIME = 10  # Seconds
    MAIL_DELTA = datetime.timedelta(minutes=10)

    MEDIA_DOCS = os.path.join(settings.MEDIA_ROOT, "documents")

    def __init__(self, *args, **kwargs):

        self.verbosity = 0

        self.file_consumer = None
        self.mail_fetcher = None

        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        try:
            self.file_consumer = Consumer(verbosity=self.verbosity)
            self.mail_fetcher = MailFetcher()
        except (ConsumerError, MailFetcherError) as e:
            raise CommandError(e)

        try:
            os.makedirs(self.MEDIA_DOCS)
        except FileExistsError:
            pass

        try:
            while True:
                self.loop()
                time.sleep(self.LOOP_TIME)
                if self.verbosity > 1:
                    print(".")
        except KeyboardInterrupt:
            print("Exiting")

    def loop(self):

        # Consume whatever files we can
        self.file_consumer.consume()

        # Occasionally fetch mail and store it to be consumed on the next loop
        delta = self.mail_fetcher.last_checked + self.MAIL_DELTA
        if delta < datetime.datetime.now():
            self.mail_fetcher.pull()
