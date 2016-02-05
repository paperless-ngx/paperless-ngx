import datetime
import email
import imaplib

from base64 import b64decode
from io import BytesIO

from django.conf import settings

from . import Consumer


class MailConsumerError(Exception):
    pass


class MailConsumer(Consumer):

    def __init__(self, *args, **kwargs):

        Consumer.__init__(self, *args, **kwargs)

        self._connection = None
        self._host = settings.MAIL_CONSUMPTION["HOST"]
        self._port = settings.MAIL_CONSUMPTION["PORT"]
        self._username = settings.MAIL_CONSUMPTION["USERNAME"]
        self._password = settings.MAIL_CONSUMPTION["PASSWORD"]
        self._inbox = settings.MAIL_CONSUMPTION["INBOX"]

        self._enabled = bool(self._host)

        self.last_checked = datetime.datetime.now()

    def _connect(self):
        self._connection = imaplib.IMAP4_SSL(self._host, self._port)

    def _login(self):

        login = self._connection.login(self._username, self._password)
        if not login[0] == "OK":
            raise MailConsumerError("Can't log into mail: {}".format(login[1]))

        inbox = self._connection.select("INBOX")
        if not inbox[0] == "OK":
            raise MailConsumerError("Can't find the inbox: {}".format(inbox[1]))

    def _fetch(self):
        for num in self._connection.search(None, "ALL")[1][0].split():
            typ, data = self._connection.fetch(num, "(RFC822)")
            # self._connection.store(num, "+FLAGS", "\\Deleted")
            yield data[0][1]

    def consume(self):

        if self._enabled:
            for message in self.get_messages():
                pass

        self.last_checked = datetime.datetime.now()

    def get_messages(self):

        self._connect()
        self._login()

        messages = []
        for data in self._fetch():
            message = self._parse_message(data)
            if message:
                messages.append(message)

        self._connection.expunge()
        self._connection.close()
        self._connection.logout()

        return messages

    @staticmethod
    def _parse_message(data):
        """
        Cribbed heavily from
        https://www.ianlewis.org/en/parsing-email-attachments-python
        """

        r = []
        message = email.message_from_string(data)

        for part in message.walk():

            content_disposition = part.get("Content-Disposition")
            if not content_disposition:
                continue

            dispositions = content_disposition.strip().split(";")
            if not dispositions[0].lower() == "attachment":
                continue

            file_data = part.get_payload()
            attachment = BytesIO(b64decode(file_data))
            attachment.content_type = part.get_content_type()
            attachment.size = len(file_data)
            attachment.name = None
            attachment.create_date = None
            attachment.mod_date = None
            attachment.read_date = None

            for param in dispositions[1:]:

                name, value = param.split("=")
                name = name.lower()

                if name == "filename":
                    attachment.name = value
                elif name == "create-date":
                    attachment.create_date = value
                elif name == "modification-date":
                    attachment.mod_date = value
                elif name == "read-date":
                    attachment.read_date = value

            r.append({
                "subject": message.get("Subject"),
                "attachment": attachment,
            })

        return r
