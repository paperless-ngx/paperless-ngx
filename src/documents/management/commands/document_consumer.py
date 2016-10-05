import datetime
import logging
import os
import time

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth.models import User
from django.dispatch import receiver

from ...models import Document
from ...consumer import Consumer, ConsumerError
from ...mail import MailFetcher, MailFetcherError
from ...signals import document_consumption_finished


class Command(BaseCommand):
    """
    On every iteration of an infinite loop, consume what we can from the
    consumption directory, and fetch any mail available.
    """
    CONSUME_USER_ID = 1
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
            self.file_consumer = Consumer()
            self.mail_fetcher = MailFetcher()
        except (ConsumerError, MailFetcherError) as e:
            raise CommandError(e)

        try:
            os.makedirs(self.MEDIA_DOCS)
        except FileExistsError:
            pass

        logging.getLogger(__name__).info(
            "Starting document consumer at {}".format(settings.CONSUMPTION_DIR)
        )

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

    @receiver(document_consumption_finished)
    def notify_finished(sender, document=None, logging_group=None, **kwargs):
        doctype = ContentType.objects.get_for_model(Document)
        user = User.objects.get(**{'id': Command.CONSUME_USER_ID})

        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=doctype.pk,
            object_id=document.pk,
            object_repr=repr(document),
            action_flag=ADDITION,
            change_message='Document %s consumption finished' % document.title
        )
