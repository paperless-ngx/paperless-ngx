import datetime
import email
import imaplib
import os
import re

from base64 import b64decode

from django.conf import settings

from . import Consumer


class MailConsumerError(Exception):
    pass


class Message(object):
    """
    A crude, but simple email message class.  We assume that there's a subject
    and exactly one attachment, and that we don't care about the message body.
    """

    SAFE_SUBJECT_REGEX = re.compile(r"^[\w\- ,.]+$")
    SAFE_SUFFIX_REGEX = re.compile(
        r"^(application/(pdf))|(image/(png|jpg|gif|tiff))$")

    def __init__(self, subject, attachment):

        self.subject = subject
        self.attachment = attachment
        self.suffix = None

        m = self.SAFE_SUFFIX_REGEX.match(attachment.content_type)
        if not m:
            raise MailConsumerError(
                "Not-awesome file type: {}".format(attachment.content_type))
        self.suffix = m.group(1) or m.group(3)

    @property
    def file_name(self):
        if self.SAFE_SUFFIX_REGEX.match(self.subject):
            return "{}.{}".format(self.subject, self.suffix)


class Attachment(object):

    def __init__(self, data):
        self.content_type = None
        self.size = None
        self.name = None
        self.created = None
        self.modified = None
        self.data = data


class MailFetcher(object):

    def __init__(self):

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
        """
        We don't actually consume here 'cause it's much easier to do that with
        files and we already have a FileConsumer.  So instead, we simply write
        the attachment to the consumption directory as a file with the proper
        format so the FileConsumer can do its job.
        """

        if self._enabled:

            for message in self.get_messages():

                t = message.attachment.created or \
                    message.attachment.modified or \
                    datetime.datetime.now()

                file_name = os.path.join(Consumer.CONSUME, message.file_name)
                with open(file_name, "wb") as f:
                    f.write(message.attachment.data)
                    os.utime(file_name, times=(t, t))

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
            attachment = Attachment(b64decode(file_data))
            attachment.content_type = part.get_content_type()
            attachment.size = len(file_data)

            for param in dispositions[1:]:

                name, value = param.split("=")
                name = name.lower()

                if name == "filename":
                    attachment.name = value
                elif name == "create-date":
                    attachment.created = value
                elif name == "modification-date":
                    attachment.modified = value

            r.append(Message(message.get("Subject"), attachment))

        return r
