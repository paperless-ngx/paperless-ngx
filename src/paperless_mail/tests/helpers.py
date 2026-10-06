import dataclasses
import email.message
import uuid
from contextlib import AbstractContextManager

from imap_tools import MailboxFolderSelectError
from imap_tools import MailboxLoginError
from imap_tools import MailMessage
from imap_tools import MailMessageFlags


@dataclasses.dataclass
class _AttachmentDef:
    filename: str = "a_file.pdf"
    maintype: str = "application/pdf"
    subtype: str = "pdf"
    disposition: str = "attachment"
    content: bytes = b"a PDF document"


class BogusFolderManager:
    current_folder = "INBOX"
    uidvalidity = "1"

    def set(self, new_folder) -> None:
        if new_folder not in ["INBOX", "spam"]:
            raise MailboxFolderSelectError(None, "uhm")
        self.current_folder = new_folder

    def status(self, folder, options):
        return {"UIDVALIDITY": self.uidvalidity}


class BogusClient:
    def __init__(self, messages) -> None:
        self.messages: list[MailMessage] = messages
        self.capabilities: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def authenticate(self, mechanism, authobject) -> None:
        # authobject must be a callable object
        auth_bytes = authobject(None)
        if auth_bytes != b"\x00admin\x00w57\xc3\xa4\xc3\xb6\xc3\xbcw4b6huwb6nhu":
            raise MailboxLoginError("BAD", "OK")

    def uid(self, command, *args) -> None:
        if command == "STORE":
            for message in self.messages:
                if message.uid == args[0]:
                    flag = args[2]
                    if flag == "processed":
                        message._raw_flag_data.append(b"+FLAGS (processed)")
                        if hasattr(message, "flags"):
                            del message.flags


class BogusMailBox(AbstractContextManager):
    # Common values so tests don't need to remember an accepted login
    USERNAME: str = "admin"
    ASCII_PASSWORD: str = "secret"
    # Note the non-ascii characters here
    UTF_PASSWORD: str = "w57äöüw4b6huwb6nhu"
    # A dummy access token
    ACCESS_TOKEN = "ea7e075cd3acf2c54c48e600398d5d5a"

    def __init__(self) -> None:
        self.messages: list[MailMessage] = []
        self.messages_spam: list[MailMessage] = []
        self.folder = BogusFolderManager()
        self.client = BogusClient(self.messages)
        self._host = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def updateClient(self) -> None:
        self.client = BogusClient(self.messages)

    def login(self, username, password) -> None:
        # This will raise a UnicodeEncodeError if the password is not ASCII only
        password.encode("ascii")
        # Otherwise, check for correct values
        if username != self.USERNAME or password != self.ASCII_PASSWORD:
            raise MailboxLoginError("BAD", "OK")

    def login_utf8(self, username, password) -> None:
        # Expected to only be called with the UTF-8 password
        if username != self.USERNAME or password != self.UTF_PASSWORD:
            raise MailboxLoginError("BAD", "OK")

    def xoauth2(self, username: str, access_token: str) -> None:
        if username != self.USERNAME or access_token != self.ACCESS_TOKEN:
            raise MailboxLoginError("BAD", "OK")

    def fetch(
        self,
        criteria="ALL",
        charset="",
        *,
        mark_seen=True,
        bulk=True,
        uid_list=None,
    ):
        if uid_list is not None:
            return [m for m in self.messages if m.uid in uid_list]
        return self._filter_messages(criteria)

    def uids(self, criteria, charset="") -> list[str]:
        return [m.uid for m in self._filter_messages(criteria)]

    def _filter_messages(self, criteria):
        msg = self.messages

        criteria = str(criteria).strip("()").split(" ")

        if "UNSEEN" in criteria:
            msg = filter(lambda m: not m.seen, msg)

        if "SUBJECT" in criteria:
            subject = criteria[criteria.index("SUBJECT") + 1].strip('"')
            msg = filter(lambda m: subject in m.subject, msg)

        if "BODY" in criteria:
            body = criteria[criteria.index("BODY") + 1].strip('"')
            msg = filter(lambda m: body in m.text, msg)

        if "FROM" in criteria:
            from_ = criteria[criteria.index("FROM") + 1].strip('"')
            msg = filter(lambda m: from_ in m.from_, msg)

        if "TO" in criteria:
            to_ = criteria[criteria.index("TO") + 1].strip('"')
            msg = filter(lambda m: any(to_ in to_addr for to_addr in m.to), msg)

        if "UNFLAGGED" in criteria:
            msg = filter(lambda m: not m.flagged, msg)

        if "UNKEYWORD" in criteria:
            tag = criteria[criteria.index("UNKEYWORD") + 1].strip("'")
            msg = filter(lambda m: tag not in m.flags, msg)

        if "(X-GM-LABELS" in criteria:  # ['NOT', '(X-GM-LABELS', '"processed"']
            msg = filter(lambda m: "processed" not in m.flags, msg)

        if "UID" in criteria:
            uid_list = criteria[criteria.index("UID") + 1].split(",")
            msg = filter(lambda m: m.uid in uid_list, msg)

        return list(msg)

    def delete(self, uid_list) -> None:
        self.messages = list(filter(lambda m: m.uid not in uid_list, self.messages))

    def flag(self, uid_list, flag_set, value) -> None:
        for message in self.messages:
            if message.uid in uid_list:
                for flag in flag_set:
                    if flag == MailMessageFlags.FLAGGED:
                        message.flagged = value
                    if flag == MailMessageFlags.SEEN:
                        message.seen = value
                    if flag == "processed":
                        message._raw_flag_data.append(b"+FLAGS (processed)")
                        if hasattr(message, "flags"):
                            del message.flags

    def move(self, uid_list, folder) -> None:
        if folder == "spam":
            self.messages_spam += list(
                filter(lambda m: m.uid in uid_list, self.messages),
            )
            self.messages = list(filter(lambda m: m.uid not in uid_list, self.messages))
        else:
            raise Exception


def fake_magic_from_buffer(buffer, *, mime=False):
    if mime:
        if "PDF" in str(buffer):
            return "application/pdf"
        else:
            return "unknown/type"
    else:
        return "Some verbose file description"


class MessageBuilder:
    def __init__(self) -> None:
        self._next_uid = 1

    def create_message(
        self,
        *,
        attachments: int | list[_AttachmentDef] = 1,
        body: str = "",
        subject: str = "the subject",
        from_: str = "no_one@mail.com",
        to: list[str] | None = None,
        seen: bool = False,
        flagged: bool = False,
        processed: bool = False,
    ) -> MailMessage:
        if to is None:
            to = ["tosomeone@somewhere.com"]

        email_msg = email.message.EmailMessage()
        # TODO: This does NOT set the UID
        email_msg["Message-ID"] = str(uuid.uuid4())
        email_msg["Subject"] = subject
        email_msg["From"] = from_
        email_msg["To"] = str(" ,".join(to))
        email_msg.set_content(body)

        # Either add some default number of attachments
        # or the provided attachments
        if isinstance(attachments, int):
            for i in range(attachments):
                attachment = _AttachmentDef(filename=f"file_{i}.pdf")
                email_msg.add_attachment(
                    attachment.content,
                    maintype=attachment.maintype,
                    subtype=attachment.subtype,
                    disposition=attachment.disposition,
                    filename=attachment.filename,
                )
        else:
            for attachment in attachments:
                email_msg.add_attachment(
                    attachment.content,
                    maintype=attachment.maintype,
                    subtype=attachment.subtype,
                    disposition=attachment.disposition,
                    filename=attachment.filename,
                )

        # Convert the EmailMessage to an imap_tools MailMessage
        imap_msg = MailMessage.from_bytes(email_msg.as_bytes())

        # TODO: Unsure how to add a uid to the actual EmailMessage. This hacks it in,
        #  based on how imap_tools uses regex to extract it.
        #  This should be a large enough pool
        uid = self._next_uid
        self._next_uid += 1

        imap_msg._raw_uid_data = f"UID {uid}".encode()

        imap_msg.seen = seen
        imap_msg.flagged = flagged
        if processed:
            imap_msg._raw_flag_data.append(b"+FLAGS (processed)")
            if hasattr(imap_msg, "flags"):
                del imap_msg.flags

        return imap_msg
