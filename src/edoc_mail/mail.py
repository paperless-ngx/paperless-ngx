import datetime
import itertools
import logging
import os
import ssl
import tempfile
import traceback
from datetime import date
from datetime import timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional
from typing import Union

import magic
import pathvalidate
from celery import chord
from celery import shared_task
from celery.canvas import Signature
from django.conf import settings
from django.db import DatabaseError
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware
from imap_tools import AND
from imap_tools import NOT
from imap_tools import MailAttachment
from imap_tools import MailBox
from imap_tools import MailboxFolderSelectError
from imap_tools import MailBoxUnencrypted
from imap_tools import MailMessage
from imap_tools import MailMessageFlags
from imap_tools.mailbox import MailBoxTls
from imap_tools.query import LogicOperator

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.loggers import LoggingMixin
from documents.models import Correspondent
from documents.parsers import is_mime_type_supported
from documents.tasks import consume_file
from edoc_mail.models import MailAccount
from edoc_mail.models import MailRule
from edoc_mail.models import ProcessedMail

# Apple Mail sets multiple IMAP KEYWORD and the general "\Flagged" FLAG
# imaplib => conn.fetch(b"<message_id>", "FLAGS")

# no flag   - (FLAGS (\\Seen $NotJunk NotJunk))'
# red       - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk))'
# orange    - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit0))'
# yellow    - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit1))'
# blue      - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit2))'
# green     - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit0 $MailFlagBit1))'
# violet    - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit0 $MailFlagBit2))'
# grey      - (FLAGS (\\Flagged \\Seen $NotJunk NotJunk $MailFlagBit1 $MailFlagBit2))'

APPLE_MAIL_TAG_COLORS = {
    "red": [],
    "orange": ["$MailFlagBit0"],
    "yellow": ["$MailFlagBit1"],
    "blue": ["$MailFlagBit2"],
    "green": ["$MailFlagBit0", "$MailFlagBit1"],
    "violet": ["$MailFlagBit0", "$MailFlagBit2"],
    "grey": ["$MailFlagBit1", "$MailFlagBit2"],
}


class MailError(Exception):
    pass


class BaseMailAction:
    """
    Base class for mail actions. A mail action is performed on a mail after
    consumption of the document is complete and is used to signal to the user
    that this mail was processed by edocedoc via the mail client.

    Furthermore, mail actions reduce the amount of mails to be analyzed by
    excluding mails on which the action was already performed (i.e., excluding
    read mails when the action is to mark mails as read).
    """

    def get_criteria(self) -> Union[dict, LogicOperator]:
        """
        Returns filtering criteria/query for this mail action.
        """
        return {}

    def post_consume(
        self,
        M: MailBox,
        message_uid: str,
        parameter: str,
    ):  # pragma: no cover
        """
        Perform mail action on the given mail uid in the mailbox.
        """
        raise NotImplementedError


class DeleteMailAction(BaseMailAction):
    """
    A mail action that deletes mails after processing.
    """

    def post_consume(self, M: MailBox, message_uid: str, parameter: str):
        M.delete(message_uid)


class MarkReadMailAction(BaseMailAction):
    """
    A mail action that marks mails as read after processing.
    """

    def get_criteria(self):
        return {"seen": False}

    def post_consume(self, M: MailBox, message_uid: str, parameter: str):
        M.flag(message_uid, [MailMessageFlags.SEEN], True)


class MoveMailAction(BaseMailAction):
    """
    A mail action that moves mails to a different folder after processing.
    """

    def post_consume(self, M, message_uid, parameter):
        M.move(message_uid, parameter)


class FlagMailAction(BaseMailAction):
    """
    A mail action that marks mails as important ("star") after processing.
    """

    def get_criteria(self):
        return {"flagged": False}

    def post_consume(self, M: MailBox, message_uid: str, parameter: str):
        M.flag(message_uid, [MailMessageFlags.FLAGGED], True)


class TagMailAction(BaseMailAction):
    """
    A mail action that tags mails after processing.
    """

    def __init__(self, parameter: str, supports_gmail_labels: bool):
        # The custom tag should look like "apple:<color>"
        if "apple:" in parameter.lower():
            _, self.color = parameter.split(":")
            self.color = self.color.strip()

            if self.color.lower() not in APPLE_MAIL_TAG_COLORS:
                raise MailError("Not a valid AppleMail tag color.")

            self.keyword = None

        else:
            self.keyword = parameter
            self.color = None
        self.supports_gmail_labels = supports_gmail_labels

    def get_criteria(self):
        # AppleMail: We only need to check if mails are \Flagged
        if self.color:
            return {"flagged": False}
        elif self.keyword:
            if self.supports_gmail_labels:
                return AND(NOT(gmail_label=self.keyword), no_keyword=self.keyword)
            else:
                return {"no_keyword": self.keyword}
        else:  # pragma: no cover
            raise ValueError("This should never happen.")

    def post_consume(self, M: MailBox, message_uid: str, parameter: str):
        if self.supports_gmail_labels:
            M.client.uid("STORE", message_uid, "+X-GM-LABELS", self.keyword)

        # AppleMail
        elif self.color:
            # Remove all existing $MailFlagBits
            M.flag(
                message_uid,
                set(itertools.chain(*APPLE_MAIL_TAG_COLORS.values())),
                False,
            )

            # Set new $MailFlagBits
            M.flag(message_uid, APPLE_MAIL_TAG_COLORS.get(self.color), True)

            # Set the general \Flagged
            # This defaults to the "red" flag in AppleMail and
            # "stars" in Thunderbird or GMail
            M.flag(message_uid, [MailMessageFlags.FLAGGED], True)

        elif self.keyword:
            M.flag(message_uid, [self.keyword], True)

        else:
            raise MailError("No keyword specified.")


def mailbox_login(mailbox: MailBox, account: MailAccount):
    logger = logging.getLogger("edoc_mail")

    try:
        if account.is_token:
            mailbox.xoauth2(account.username, account.password)
        else:
            try:
                _ = account.password.encode("ascii")
                use_ascii_login = True
            except UnicodeEncodeError:
                use_ascii_login = False

            if use_ascii_login:
                mailbox.login(account.username, account.password)
            else:
                logger.debug("Falling back to AUTH=PLAIN")
                mailbox.login_utf8(account.username, account.password)

    except Exception as e:
        logger.error(
            f"Error while authenticating account {account}: {e}",
            exc_info=False,
        )
        raise MailError(
            f"Error while authenticating account {account}",
        ) from e


@shared_task
def apply_mail_action(
    result: list[str],
    rule_id: int,
    message_uid: str,
    message_subject: str,
    message_date: datetime.datetime,
):
    """
    This shared task applies the mail action of a particular mail rule to the
    given mail. Creates a ProcessedMail object, so that the mail won't be
    processed in the future.
    """

    rule = MailRule.objects.get(pk=rule_id)
    account = MailAccount.objects.get(pk=rule.account.pk)

    # Ensure the date is properly timezone aware
    if is_naive(message_date):
        message_date = make_aware(message_date)

    try:
        with get_mailbox(
            server=account.imap_server,
            port=account.imap_port,
            security=account.imap_security,
        ) as M:
            # Need to know the support for the possible tagging
            supports_gmail_labels = "X-GM-EXT-1" in M.client.capabilities

            mailbox_login(M, account)
            M.folder.set(rule.folder)

            action = get_rule_action(rule, supports_gmail_labels)
            action.post_consume(M, message_uid, rule.action_parameter)

        ProcessedMail.objects.create(
            owner=rule.owner,
            rule=rule,
            folder=rule.folder,
            uid=message_uid,
            subject=message_subject,
            received=message_date,
            status="SUCCESS",
        )

    except Exception:
        ProcessedMail.objects.create(
            owner=rule.owner,
            rule=rule,
            folder=rule.folder,
            uid=message_uid,
            subject=message_subject,
            received=message_date,
            status="FAILED",
            error=traceback.format_exc(),
        )
        raise


@shared_task
def error_callback(
    request,
    exc,
    tb,
    rule_id: int,
    message_uid: str,
    message_subject: str,
    message_date: datetime.datetime,
):
    """
    A shared task that is called whenever something goes wrong during
    consumption of a file. See queue_consumption_tasks.
    """
    rule = MailRule.objects.get(pk=rule_id)

    ProcessedMail.objects.create(
        rule=rule,
        folder=rule.folder,
        uid=message_uid,
        subject=message_subject,
        received=message_date,
        status="FAILED",
        error=traceback.format_exc(),
    )


def queue_consumption_tasks(
    *,
    consume_tasks: list[Signature],
    rule: MailRule,
    message: MailMessage,
):
    """
    Queue a list of consumption tasks (Signatures for the consume_file shared
    task) with celery.
    """

    mail_action_task = apply_mail_action.s(
        rule_id=rule.pk,
        message_uid=message.uid,
        message_subject=message.subject,
        message_date=message.date,
    )
    chord(header=consume_tasks, body=mail_action_task).on_error(
        error_callback.s(
            rule_id=rule.pk,
            message_uid=message.uid,
            message_subject=message.subject,
            message_date=message.date,
        ),
    ).delay()


def get_rule_action(rule: MailRule, supports_gmail_labels: bool) -> BaseMailAction:
    """
    Returns a BaseMailAction instance for the given rule.
    """

    if rule.action == MailRule.MailAction.FLAG:
        return FlagMailAction()
    elif rule.action == MailRule.MailAction.DELETE:
        return DeleteMailAction()
    elif rule.action == MailRule.MailAction.MOVE:
        return MoveMailAction()
    elif rule.action == MailRule.MailAction.MARK_READ:
        return MarkReadMailAction()
    elif rule.action == MailRule.MailAction.TAG:
        return TagMailAction(rule.action_parameter, supports_gmail_labels)
    else:
        raise NotImplementedError("Unknown action.")  # pragma: no cover


def make_criterias(rule: MailRule, supports_gmail_labels: bool):
    """
    Returns criteria to be applied to MailBox.fetch for the given rule.
    """

    maximum_age = date.today() - timedelta(days=rule.maximum_age)
    criterias = {}
    if rule.maximum_age > 0:
        criterias["date_gte"] = maximum_age
    if rule.filter_from:
        criterias["from_"] = rule.filter_from
    if rule.filter_to:
        criterias["to"] = rule.filter_to
    if rule.filter_subject:
        criterias["subject"] = rule.filter_subject
    if rule.filter_body:
        criterias["body"] = rule.filter_body

    rule_query = get_rule_action(rule, supports_gmail_labels).get_criteria()
    if isinstance(rule_query, dict):
        if len(rule_query) or len(criterias):
            return AND(**rule_query, **criterias)
        else:
            return "ALL"
    else:
        return AND(rule_query, **criterias)


def get_mailbox(server, port, security) -> MailBox:
    """
    Returns the correct MailBox instance for the given configuration.
    """
    ssl_context = ssl.create_default_context()
    if settings.EMAIL_CERTIFICATE_FILE is not None:  # pragma: no cover
        ssl_context.load_verify_locations(cafile=settings.EMAIL_CERTIFICATE_FILE)

    if security == MailAccount.ImapSecurity.NONE:
        mailbox = MailBoxUnencrypted(server, port)
    elif security == MailAccount.ImapSecurity.STARTTLS:
        mailbox = MailBoxTls(server, port, ssl_context=ssl_context)
    elif security == MailAccount.ImapSecurity.SSL:
        mailbox = MailBox(server, port, ssl_context=ssl_context)
    else:
        raise NotImplementedError("Unknown IMAP security")  # pragma: no cover
    return mailbox


class MailAccountHandler(LoggingMixin):
    """
    The main class that handles mail accounts.

    * processes all rules for a given mail account
    * for each mail rule, fetches relevant mails, and queues documents from
      matching mails for consumption
    * marks processed mails in the database, so that they won't be processed
      again
    * runs mail actions on the mail server, when consumption is completed
    """

    logging_name = "edoc_mail"

    def _correspondent_from_name(self, name: str) -> Optional[Correspondent]:
        try:
            return Correspondent.objects.get_or_create(name=name)[0]
        except DatabaseError as e:
            self.log.error(f"Error while retrieving correspondent {name}: {e}")
            return None

    def _get_title(
        self,
        message: MailMessage,
        att: MailAttachment,
        rule: MailRule,
    ) -> Optional[str]:
        if rule.assign_title_from == MailRule.TitleSource.FROM_SUBJECT:
            return message.subject

        elif rule.assign_title_from == MailRule.TitleSource.FROM_FILENAME:
            return os.path.splitext(os.path.basename(att.filename))[0]

        elif rule.assign_title_from == MailRule.TitleSource.NONE:
            return None

        else:
            raise NotImplementedError(
                "Unknown title selector.",
            )  # pragma: no cover

    def _get_correspondent(
        self,
        message: MailMessage,
        rule: MailRule,
    ) -> Optional[Correspondent]:
        c_from = rule.assign_correspondent_from

        if c_from == MailRule.CorrespondentSource.FROM_NOTHING:
            return None

        elif c_from == MailRule.CorrespondentSource.FROM_EMAIL:
            return self._correspondent_from_name(message.from_)

        elif c_from == MailRule.CorrespondentSource.FROM_NAME:
            from_values = message.from_values
            if from_values is not None and len(from_values.name) > 0:
                return self._correspondent_from_name(from_values.name)
            else:
                return self._correspondent_from_name(message.from_)

        elif c_from == MailRule.CorrespondentSource.FROM_CUSTOM:
            return rule.assign_correspondent

        else:
            raise NotImplementedError(
                "Unknown correspondent selector",
            )  # pragma: no cover

    def handle_mail_account(self, account: MailAccount):
        """
        Main entry method to handle a specific mail account.
        """

        self.renew_logging_group()

        self.log.debug(f"Processing mail account {account}")

        total_processed_files = 0
        try:
            with get_mailbox(
                account.imap_server,
                account.imap_port,
                account.imap_security,
            ) as M:
                supports_gmail_labels = "X-GM-EXT-1" in M.client.capabilities
                supports_auth_plain = "AUTH=PLAIN" in M.client.capabilities

                self.log.debug(f"GMAIL Label Support: {supports_gmail_labels}")
                self.log.debug(f"AUTH=PLAIN Support: {supports_auth_plain}")

                mailbox_login(M, account)

                self.log.debug(
                    f"Account {account}: Processing "
                    f"{account.rules.count()} rule(s)",
                )

                for rule in account.rules.order_by("order"):
                    try:
                        total_processed_files += self._handle_mail_rule(
                            M,
                            rule,
                            supports_gmail_labels,
                        )
                    except Exception as e:
                        self.log.exception(
                            f"Rule {rule}: Error while processing rule: {e}",
                        )
        except MailError:
            raise
        except Exception as e:
            self.log.error(
                f"Error while retrieving mailbox {account}: {e}",
                exc_info=False,
            )

        return total_processed_files

    def _handle_mail_rule(
        self,
        M: MailBox,
        rule: MailRule,
        supports_gmail_labels: bool,
    ):
        self.log.debug(f"Rule {rule}: Selecting folder {rule.folder}")

        try:
            M.folder.set(rule.folder)
        except MailboxFolderSelectError as err:
            self.log.error(
                f"Unable to access folder {rule.folder}, attempting folder listing",
            )
            try:
                for folder_info in M.folder.list():
                    self.log.info(f"Located folder: {folder_info.name}")
            except Exception as e:
                self.log.error(
                    "Exception during folder listing, unable to provide list folders: "
                    + str(e),
                )

            raise MailError(
                f"Rule {rule}: Folder {rule.folder} "
                f"does not exist in account {rule.account}",
            ) from err

        criterias = make_criterias(rule, supports_gmail_labels)

        self.log.debug(
            f"Rule {rule}: Searching folder with criteria {criterias}",
        )

        try:
            messages = M.fetch(
                criteria=criterias,
                mark_seen=False,
                charset=rule.account.character_set,
                bulk=True,
            )
        except Exception as err:
            raise MailError(
                f"Rule {rule}: Error while fetching folder {rule.folder}",
            ) from err

        mails_processed = 0
        total_processed_files = 0

        for message in messages:
            if ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).exists():
                self.log.debug(f"Skipping mail {message}, already processed.")
                continue

            try:
                processed_files = self._handle_message(message, rule)

                total_processed_files += processed_files
                mails_processed += 1
            except Exception as e:
                self.log.exception(
                    f"Rule {rule}: Error while processing mail {message.uid}: {e}",
                )

        self.log.debug(f"Rule {rule}: Processed {mails_processed} matching mail(s)")

        return total_processed_files

    def _handle_message(self, message, rule: MailRule) -> int:
        processed_elements = 0

        # Skip Message handling when only attachments are to be processed but
        # message doesn't have any.
        if (
            not message.attachments
            and rule.consumption_scope == MailRule.ConsumptionScope.ATTACHMENTS_ONLY
        ):
            return processed_elements

        self.log.debug(
            f"Rule {rule}: "
            f"Processing mail {message.subject} from {message.from_} with "
            f"{len(message.attachments)} attachment(s)",
        )

        tag_ids: list[int] = [tag.id for tag in rule.assign_tags.all()]
        doc_type = rule.assign_document_type

        if (
            rule.consumption_scope == MailRule.ConsumptionScope.EML_ONLY
            or rule.consumption_scope == MailRule.ConsumptionScope.EVERYTHING
        ):
            processed_elements += self._process_eml(
                message,
                rule,
                tag_ids,
                doc_type,
            )

        if (
            rule.consumption_scope == MailRule.ConsumptionScope.ATTACHMENTS_ONLY
            or rule.consumption_scope == MailRule.ConsumptionScope.EVERYTHING
        ):
            processed_elements += self._process_attachments(
                message,
                rule,
                tag_ids,
                doc_type,
            )

        return processed_elements

    def _process_attachments(
        self,
        message: MailMessage,
        rule: MailRule,
        tag_ids,
        doc_type,
    ):
        processed_attachments = 0

        consume_tasks = list()

        for att in message.attachments:
            if (
                att.content_disposition != "attachment"
                and rule.attachment_type
                == MailRule.AttachmentProcessing.ATTACHMENTS_ONLY
            ):
                self.log.debug(
                    f"Rule {rule}: "
                    f"Skipping attachment {att.filename} "
                    f"with content disposition {att.content_disposition}",
                )
                continue

            if rule.filter_attachment_filename_include and not fnmatch(
                att.filename.lower(),
                rule.filter_attachment_filename_include.lower(),
            ):
                # Force the filename and pattern to the lowercase
                # as this is system dependent otherwise
                self.log.debug(
                    f"Rule {rule}: "
                    f"Skipping attachment {att.filename} "
                    f"does not match pattern {rule.filter_attachment_filename_include}",
                )
                continue
            elif rule.filter_attachment_filename_exclude and fnmatch(
                att.filename.lower(),
                rule.filter_attachment_filename_exclude.lower(),
            ):
                # Force the filename and pattern to the lowercase
                # as this is system dependent otherwise
                self.log.debug(
                    f"Rule {rule}: "
                    f"Skipping attachment {att.filename} "
                    f"does match pattern {rule.filter_attachment_filename_exclude}",
                )
                continue

            correspondent = self._get_correspondent(message, rule)

            title = self._get_title(message, att, rule)

            # don't trust the content type of the attachment. Could be
            # generic application/octet-stream.
            mime_type = magic.from_buffer(att.payload, mime=True)

            if is_mime_type_supported(mime_type):
                self.log.info(
                    f"Rule {rule}: "
                    f"Consuming attachment {att.filename} from mail "
                    f"{message.subject} from {message.from_}",
                )

                settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

                temp_dir = Path(
                    tempfile.mkdtemp(
                        prefix="edoc-mail-",
                        dir=settings.SCRATCH_DIR,
                    ),
                )

                attachment_name = pathvalidate.sanitize_filename(att.filename)
                if attachment_name:
                    temp_filename = temp_dir / attachment_name
                else:  # pragma: no cover
                    # Some cases may have no name (generally inline)
                    temp_filename = temp_dir / "no-name-attachment"

                temp_filename.write_bytes(att.payload)

                input_doc = ConsumableDocument(
                    source=DocumentSource.MailFetch,
                    original_file=temp_filename,
                    mailrule_id=rule.pk,
                )
                doc_overrides = DocumentMetadataOverrides(
                    title=title,
                    filename=pathvalidate.sanitize_filename(att.filename),
                    correspondent_id=correspondent.id if correspondent else None,
                    document_type_id=doc_type.id if doc_type else None,
                    tag_ids=tag_ids,
                    owner_id=(
                        rule.owner.id
                        if (rule.assign_owner_from_rule and rule.owner)
                        else None
                    ),
                )

                consume_task = consume_file.s(
                    input_doc,
                    doc_overrides,
                )

                consume_tasks.append(consume_task)

                processed_attachments += 1
            else:
                self.log.debug(
                    f"Rule {rule}: "
                    f"Skipping attachment {att.filename} "
                    f"since guessed mime type {mime_type} is not supported "
                    f"by edoc",
                )

        if len(consume_tasks) > 0:
            queue_consumption_tasks(
                consume_tasks=consume_tasks,
                rule=rule,
                message=message,
            )
        else:
            # No files to consume, just mark as processed if it wasn't by .eml processing
            if not ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).exists():
                ProcessedMail.objects.create(
                    rule=rule,
                    folder=rule.folder,
                    uid=message.uid,
                    subject=message.subject,
                    received=message.date,
                    status="PROCESSED_WO_CONSUMPTION",
                )

        return processed_attachments

    def _process_eml(
        self,
        message: MailMessage,
        rule: MailRule,
        tag_ids,
        doc_type,
    ):
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        _, temp_filename = tempfile.mkstemp(
            prefix="edoc-mail-",
            dir=settings.SCRATCH_DIR,
            suffix=".eml",
        )
        with open(temp_filename, "wb") as f:
            # Move "From"-header to beginning of file
            # TODO: This ugly workaround is needed because the parser is
            #   chosen only by the mime_type detected via magic
            #   (see documents/consumer.py "mime_type = magic.from_file")
            #   Unfortunately magic sometimes fails to detect the mime
            #   type of .eml files correctly as message/rfc822 and instead
            #   detects text/plain.
            #   This also effects direct file consumption of .eml files
            #   which are not treated with this workaround.
            from_element = None
            for i, header in enumerate(message.obj._headers):
                if header[0] == "From":
                    from_element = i
            if from_element:
                new_headers = [message.obj._headers.pop(from_element)]
                new_headers += message.obj._headers
                message.obj._headers = new_headers

            f.write(message.obj.as_bytes())

        correspondent = self._get_correspondent(message, rule)

        self.log.info(
            f"Rule {rule}: "
            f"Consuming eml from mail "
            f"{message.subject} from {message.from_}",
        )

        input_doc = ConsumableDocument(
            source=DocumentSource.MailFetch,
            original_file=temp_filename,
            mailrule_id=rule.pk,
        )
        doc_overrides = DocumentMetadataOverrides(
            title=message.subject,
            filename=pathvalidate.sanitize_filename(f"{message.subject}.eml"),
            correspondent_id=correspondent.id if correspondent else None,
            document_type_id=doc_type.id if doc_type else None,
            tag_ids=tag_ids,
            owner_id=rule.owner.id if rule.owner else None,
        )

        consume_task = consume_file.s(
            input_doc,
            doc_overrides,
        )

        queue_consumption_tasks(
            consume_tasks=[consume_task],
            rule=rule,
            message=message,
        )

        processed_elements = 1
        return processed_elements
