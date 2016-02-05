import datetime
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...consumers import (
    FileConsumer, FileConsumerError, MailConsumer, MailConsumerError)


class Command(BaseCommand):
    """
    Loop over every file found in CONSUMPTION_DIR and:
      1. Convert it to a greyscale png
      2. Use tesseract on the png
      3. Encrypt and store the document in the MEDIA_ROOT
      4. Store the OCR'd text in the database
      5. Delete the document and image(s)
    """

    LOOP_TIME = 10  # Seconds
    MAIL_DELTA = datetime.timedelta(minutes=10)

    MEDIA_DOCS = os.path.join(settings.MEDIA_ROOT, "documents")

    def __init__(self, *args, **kwargs):

        self.verbosity = 0

        self.file_consumer = None
        self.mail_consumer = None

        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        try:
            self.file_consumer = FileConsumer(verbosity=self.verbosity)
            self.mail_consumer = MailConsumer(verbosity=self.verbosity)
        except (FileConsumerError, MailConsumerError) as e:
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

        self.file_consumer.consume()

        delta = self.mail_consumer.last_checked + self.MAIL_DELTA
        if delta > datetime.datetime.now():
            self.mail_consumer.consume()

    def _render(self, text, verbosity):
        if self.verbosity >= verbosity:
            print(text)
