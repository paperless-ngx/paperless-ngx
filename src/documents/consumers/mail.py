import datetime
import imaplib

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
            self.get_messages()

        self.last_checked = datetime.datetime.now()

    def get_messages(self):

        self._connect()
        self._login()

        for message in self._fetch():
            print(message)  # Now we have to do something with the attachment

        self._connection.expunge()
        self._connection.close()
        self._connection.logout()

    def _guess_file_attributes(self, doc):
        return None, None, "jpg"
