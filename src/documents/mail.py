import datetime
import imaplib
import logging
import os
import re
import time
import uuid

from base64 import b64decode
from email import policy
from email.parser import BytesParser
from dateutil import parser

from django.conf import settings

from .models import Correspondent


class MailFetcherError(Exception):
    pass


class InvalidMessageError(MailFetcherError):
    pass


class Loggable(object):

    def __init__(self, group=None):
        self.logger = logging.getLogger(__name__)
        self.logging_group = group or uuid.uuid4()

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })


class Message(Loggable):
    """
    A crude, but simple email message class.  We assume that there's a subject
    and n attachments, and that we don't care about the message body.
    """

    SECRET = os.getenv("PAPERLESS_EMAIL_SECRET")

    def __init__(self, data, group=None):
        """
        Cribbed heavily from
        https://www.ianlewis.org/en/parsing-email-attachments-python
        """

        Loggable.__init__(self, group=group)

        self.subject = None
        self.time = None
        self.attachment = None

        message = BytesParser(policy=policy.default).parsebytes(data)
        self.subject = str(message["Subject"]).replace("\r\n", "")
        self.body = str(message.get_body())

        self.check_subject()
        self.check_body()

        self._set_time(message)

        self.log("info", 'Importing email: "{}"'.format(self.subject))

        attachments = []
        for part in message.walk():

            content_disposition = part.get("Content-Disposition")
            if not content_disposition:
                continue

            dispositions = content_disposition.strip().split(";")
            if len(dispositions) < 2:
                continue

            if not dispositions[0].lower() == "attachment" and \
               "filename" not in dispositions[1].lower():
                continue

            file_data = part.get_payload()

            attachments.append(Attachment(
                b64decode(file_data), content_type=part.get_content_type()))

        if len(attachments) == 0:
            raise InvalidMessageError(
                "There don't appear to be any attachments to this message")

        if len(attachments) > 1:
            raise InvalidMessageError(
                "There's more than one attachment to this message. It cannot "
                "be indexed automatically."
            )

        self.attachment = attachments[0]

    def __bool__(self):
        return bool(self.attachment)

    def check_subject(self):
        if self.subject is None:
            raise InvalidMessageError("Message does not have a subject")
        if not Correspondent.SAFE_REGEX.match(self.subject):
            raise InvalidMessageError("Message subject is unsafe: {}".format(
                self.subject))

    def check_body(self):
        if self.SECRET not in self.body:
            raise InvalidMessageError("The secret wasn't in the body")

    def _set_time(self, message):
        self.time = datetime.datetime.now()
        message_time = message.get("Date")
        if message_time:
            try:
                self.time = parser.parse(message_time)
            except (ValueError, AttributeError):
                pass  # We assume that "now" is ok

    @property
    def file_name(self):
        return "{}.{}".format(self.subject, self.attachment.suffix)


class Attachment(object):

    SAFE_SUFFIX_REGEX = re.compile(
        r"^(application/(pdf))|(image/(png|jpeg|gif|tiff))$")

    def __init__(self, data, content_type):

        self.content_type = content_type
        self.data = data
        self.suffix = None

        m = self.SAFE_SUFFIX_REGEX.match(self.content_type)
        if not m:
            raise MailFetcherError(
                "Not-awesome file type: {}".format(self.content_type))
        self.suffix = m.group(2) or m.group(4)

    def read(self):
        return self.data


class MailFetcher(Loggable):

    def __init__(self, consume=settings.CONSUMPTION_DIR):

        Loggable.__init__(self)

        self._connection = None
        self._host = os.getenv("PAPERLESS_CONSUME_MAIL_HOST")
        self._port = os.getenv("PAPERLESS_CONSUME_MAIL_PORT")
        self._username = os.getenv("PAPERLESS_CONSUME_MAIL_USER")
        self._password = os.getenv("PAPERLESS_CONSUME_MAIL_PASS")
        self._inbox = os.getenv("PAPERLESS_CONSUME_MAIL_INBOX", "INBOX")

        self._enabled = bool(self._host)
        if self._enabled and Message.SECRET is None:
            raise MailFetcherError("No PAPERLESS_EMAIL_SECRET defined")

        self.last_checked = time.time()
        self.consume = consume

    def pull(self):
        """
        Fetch all available mail at the target address and store it locally in
        the consumption directory so that the file consumer can pick it up and
        do its thing.
        """

        if self._enabled:

            # Reset the grouping id for each fetch
            self.logging_group = uuid.uuid4()

            self.log("debug", "Checking mail")

            for message in self._get_messages():

                self.log("info", 'Storing email: "{}"'.format(message.subject))

                t = int(time.mktime(message.time.timetuple()))
                file_name = os.path.join(self.consume, message.file_name)
                with open(file_name, "wb") as f:
                    f.write(message.attachment.data)
                    os.utime(file_name, times=(t, t))

        self.last_checked = time.time()

    def _get_messages(self):

        r = []
        try:

            self._connect()
            self._login()

            for message in self._fetch():
                if message:
                    r.append(message)

            self._connection.expunge()
            self._connection.close()
            self._connection.logout()

        except MailFetcherError as e:
            self.log("error", str(e))

        return r

    def _connect(self):
        self._connection = imaplib.IMAP4_SSL(self._host, self._port)

    def _login(self):

        login = self._connection.login(self._username, self._password)
        if not login[0] == "OK":
            raise MailFetcherError("Can't log into mail: {}".format(login[1]))

        inbox = self._connection.select(self._inbox)
        if not inbox[0] == "OK":
            raise MailFetcherError("Can't find the inbox: {}".format(inbox[1]))

    def _fetch(self):

        for num in self._connection.search(None, "ALL")[1][0].split():

            __, data = self._connection.fetch(num, "(RFC822)")

            message = None
            try:
                message = Message(data[0][1], self.logging_group)
            except InvalidMessageError as e:
                self.log("error", str(e))
            else:
                self._connection.store(num, "+FLAGS", "\\Deleted")

            if message:
                yield message
