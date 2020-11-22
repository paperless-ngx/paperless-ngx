import os
import tempfile
from datetime import timedelta, date

import magic
from django.conf import settings
from django.utils.text import slugify
from django_q.tasks import async_task
from imap_tools import MailBox, MailBoxUnencrypted, AND, MailMessageFlags, \
    MailboxFolderSelectError

from documents.loggers import LoggingMixin
from documents.models import Correspondent
from documents.parsers import is_mime_type_supported
from paperless_mail.models import MailAccount, MailRule


class MailError(Exception):
    pass


class BaseMailAction:

    def get_criteria(self):
        return {}

    def post_consume(self, M, message_uids, parameter):
        pass


class DeleteMailAction(BaseMailAction):

    def post_consume(self, M, message_uids, parameter):
        M.delete(message_uids)


class MarkReadMailAction(BaseMailAction):

    def get_criteria(self):
        return {'seen': False}

    def post_consume(self, M, message_uids, parameter):
        M.seen(message_uids, True)


class MoveMailAction(BaseMailAction):

    def post_consume(self, M, message_uids, parameter):
        M.move(message_uids, parameter)


class FlagMailAction(BaseMailAction):

    def get_criteria(self):
        return {'flagged': False}

    def post_consume(self, M, message_uids, parameter):
        M.flag(message_uids, [MailMessageFlags.FLAGGED], True)


def get_rule_action(rule):
    if rule.action == MailRule.ACTION_FLAG:
        return FlagMailAction()
    elif rule.action == MailRule.ACTION_DELETE:
        return DeleteMailAction()
    elif rule.action == MailRule.ACTION_MOVE:
        return MoveMailAction()
    elif rule.action == MailRule.ACTION_MARK_READ:
        return MarkReadMailAction()
    else:
        raise ValueError("Unknown action.")


def make_criterias(rule):
    maximum_age = date.today() - timedelta(days=rule.maximum_age)
    criterias = {
        "date_gte": maximum_age
    }
    if rule.filter_from:
        criterias["from_"] = rule.filter_from
    if rule.filter_subject:
        criterias["subject"] = rule.filter_subject
    if rule.filter_body:
        criterias["body"] = rule.filter_body

    return {**criterias, **get_rule_action(rule).get_criteria()}


def get_title(message, att, rule):
    if rule.assign_title_from == MailRule.TITLE_FROM_SUBJECT:
        title = message.subject
    elif rule.assign_title_from == MailRule.TITLE_FROM_FILENAME:
        title = os.path.splitext(os.path.basename(att.filename))[0]
    else:
        raise ValueError("Unknown title selector.")

    return title


def get_correspondent(message, rule):
    if rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_NOTHING:
        correspondent = None
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_EMAIL:
        correspondent_name = message.from_
        correspondent = Correspondent.objects.get_or_create(
            name=correspondent_name, defaults={
                "slug": slugify(correspondent_name)
            })[0]
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_NAME:
        if message.from_values and \
           'name' in message.from_values \
           and message.from_values['name']:
            correspondent_name = message.from_values['name']
        else:
            correspondent_name = message.from_

        correspondent = Correspondent.objects.get_or_create(
            name=correspondent_name, defaults={
                "slug": slugify(correspondent_name)
            })[0]
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_CUSTOM:
        correspondent = rule.assign_correspondent
    else:
        raise ValueError("Unknwown correspondent selector")

    return correspondent


def get_mailbox(server, port, security):
    if security == MailAccount.IMAP_SECURITY_NONE:
        mailbox = MailBoxUnencrypted(server, port)
    elif security == MailAccount.IMAP_SECURITY_STARTTLS:
        mailbox = MailBox(server, port, starttls=True)
    elif security == MailAccount.IMAP_SECURITY_SSL:
        mailbox = MailBox(server, port)
    else:
        raise ValueError("Unknown IMAP security")
    return mailbox


class MailAccountHandler(LoggingMixin):

    def handle_mail_account(self, account):

        self.renew_logging_group()

        self.log('debug', f"Processing mail account {account}")

        total_processed_files = 0

        with get_mailbox(account.imap_server,
                         account.imap_port,
                         account.imap_security) as M:

            try:
                M.login(account.username, account.password)
            except Exception:
                raise MailError(
                    f"Error while authenticating account {account.name}")

            self.log('debug', f"Account {account}: Processing "
                              f"{account.rules.count()} rule(s)")

            for rule in account.rules.order_by('order'):
                self.log(
                    'debug',
                    f"Account {account}: Processing rule {rule.name}")

                self.log(
                    'debug',
                    f"Rule {account}.{rule}: Selecting folder {rule.folder}")

                try:
                    M.folder.set(rule.folder)
                except MailboxFolderSelectError:
                    raise MailError(
                        f"Rule {rule.name}: Folder {rule.folder} "
                        f"does not exist in account {account.name}")

                criterias = make_criterias(rule)

                self.log(
                    'debug',
                    f"Rule {account}.{rule}: Searching folder with criteria "
                    f"{str(AND(**criterias))}")

                try:
                    messages = M.fetch(criteria=AND(**criterias),
                                       mark_seen=False)
                except Exception:
                    raise MailError(
                        f"Rule {rule.name}: Error while fetching folder "
                        f"{rule.folder} of account {account.name}")

                post_consume_messages = []

                mails_processed = 0

                for message in messages:
                    try:
                        processed_files = self.handle_message(message, rule)
                    except Exception:
                        raise MailError(
                            f"Rule {rule.name}: Error while processing mail "
                            f"{message.uid} of account {account.name}")
                    if processed_files > 0:
                        post_consume_messages.append(message.uid)

                    total_processed_files += processed_files
                    mails_processed += 1

                self.log(
                    'debug',
                    f"Rule {account}.{rule}: Processed {mails_processed} "
                    f"matching mail(s)")

                self.log(
                    'debug',
                    f"Rule {account}.{rule}: Running mail actions on "
                    f"{len(post_consume_messages)} mails")

                try:
                    get_rule_action(rule).post_consume(
                        M,
                        post_consume_messages,
                        rule.action_parameter)

                except Exception:
                    raise MailError(
                        f"Rule {rule.name}: Error while processing "
                        f"post-consume actions for account {account.name}")

        return total_processed_files

    def handle_message(self, message, rule):
        if not message.attachments:
            return 0

        self.log(
            'debug',
            f"Rule {rule.account}.{rule}: "
            f"Processing mail {message.subject} from {message.from_} with "
            f"{len(message.attachments)} attachment(s)")

        correspondent = get_correspondent(message, rule)
        tag = rule.assign_tag
        doc_type = rule.assign_document_type

        processed_attachments = 0

        for att in message.attachments:

            if not att.content_disposition == "attachment":
                self.log(
                    'debug',
                    f"Rule {rule.account}.{rule}: "
                    f"Skipping attachment {att.filename} "
                    f"with content disposition inline")
                continue

            title = get_title(message, att, rule)

            # don't trust the content type of the attachment. Could be
            # generic application/octet-stream.
            mime_type = magic.from_buffer(att.payload, mime=True)

            if is_mime_type_supported(mime_type):

                os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
                _, temp_filename = tempfile.mkstemp(prefix="paperless-mail-",
                                                    dir=settings.SCRATCH_DIR)
                with open(temp_filename, 'wb') as f:
                    f.write(att.payload)

                self.log(
                    'info',
                    f"Rule {rule.account}.{rule}: "
                    f"Consuming attachment {att.filename} from mail "
                    f"{message.subject} from {message.from_}")

                async_task(
                    "documents.tasks.consume_file",
                    path=temp_filename,
                    override_filename=att.filename,
                    override_title=title,
                    override_correspondent_id=correspondent.id if correspondent else None,  # NOQA: E501
                    override_document_type_id=doc_type.id if doc_type else None,  # NOQA: E501
                    override_tag_ids=[tag.id] if tag else None,
                    task_name=att.filename[:100]
                )

                processed_attachments += 1
            else:
                self.log(
                    'debug',
                    f"Rule {rule.account}.{rule}: "
                    f"Skipping attachment {att.filename} "
                    f"since guessed mime type {mime_type} is not supported "
                    f"by paperless")

        return processed_attachments
