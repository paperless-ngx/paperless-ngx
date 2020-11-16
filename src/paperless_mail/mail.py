import os
import tempfile
from datetime import timedelta, date


from django.conf import settings
from django.utils.text import slugify
from django_q.tasks import async_task
from imap_tools import MailBox, MailBoxUnencrypted, AND, MailMessageFlags

from documents.models import Correspondent
from paperless_mail.models import MailAccount, MailRule


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


def get_rule_action(action):
    if action == MailRule.ACTION_FLAG:
        return FlagMailAction()
    elif action == MailRule.ACTION_DELETE:
        return DeleteMailAction()
    elif action == MailRule.ACTION_MOVE:
        return MoveMailAction()
    elif action == MailRule.ACTION_MARK_READ:
        return MarkReadMailAction()
    else:
        raise ValueError("Unknown action.")


def handle_mail_account(account):

    if account.imap_security == MailAccount.IMAP_SECURITY_NONE:
        mailbox = MailBoxUnencrypted(account.imap_server, account.imap_port)
    elif account.imap_security == MailAccount.IMAP_SECURITY_STARTTLS:
        mailbox = MailBox(account.imap_server, account.imap_port, starttls=True)
    elif account.imap_security == MailAccount.IMAP_SECURITY_SSL:
        mailbox = MailBox(account.imap_server, account.imap_port)
    else:
        raise ValueError("Unknown IMAP security")

    with mailbox.login(account.username, account.password) as M:

        for rule in account.rules.all():

            M.folder.set(rule.folder)

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

            action = get_rule_action(rule.action)
            criterias = {**criterias, **action.get_criteria()}

            messages = M.fetch(criteria=AND(**criterias), mark_seen=False)

            post_consume_messages = []

            for message in messages:
                result = handle_message(message, rule)
                if result:
                    post_consume_messages.append(message.uid)

            action.post_consume(M, post_consume_messages, rule.action_parameter)


def handle_message(message, rule):
    if not message.attachments:
        return False

    if rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_NOTHING:
        correspondent = None
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_EMAIL:
        corerspondent_name = message.from_
        correspondent = Correspondent.objects.get_or_create(
            name=corerspondent_name, defaults={
                "slug": slugify(corerspondent_name)
            })[0]
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_NAME:
        corerspondent_name = message.from_values['name'] \
            if (message.from_values and
                'name' in message.from_values and
                message.from_values['name']) else message.from_
        correspondent = Correspondent.objects.get_or_create(
            name=corerspondent_name, defaults={
                "slug": slugify(corerspondent_name)
            })[0]
    elif rule.assign_correspondent_from == MailRule.CORRESPONDENT_FROM_CUSTOM:
        correspondent = rule.assign_correspondent
    else:
        raise ValueError("Unknwown correspondent selector")

    tag = rule.assign_tag

    doc_type = rule.assign_document_type

    for att in message.attachments:

        if rule.assign_title_from == MailRule.TITLE_FROM_SUBJECT:
            title = message.subject
        elif rule.assign_title_from == MailRule.TITLE_FROM_FILENAME:
            title = att.filename
        else:
            raise ValueError("Unknown title selector.")

        if att.content_type == 'application/pdf':
            print("This is where I would consume the file with name {} and I would "
                  "give it the title '{}', correspondent '{}', tag '{}', and doc type"
                  "'{}'."
                  .format(att.filename, title, correspondent, tag, doc_type))

            os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

            _, temp_filename = tempfile.mkstemp(prefix="paperless-mail-", dir=settings.SCRATCH_DIR)

            with open(temp_filename, 'wb') as f:
                f.write(att.payload)

            async_task(
                "documents.tasks.consume_file",
                file=temp_filename,
                original_filename=att.filename,
                force_title=title,
                force_correspondent_id=correspondent.id if correspondent else None,
                force_document_type_id=doc_type.id if doc_type else None,
                force_tag_ids=[tag.id] if tag else None
            )

    return True
