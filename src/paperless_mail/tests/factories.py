from __future__ import annotations

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail


class MailAccountFactory(DjangoModelFactory[MailAccount]):
    class Meta(DjangoModelFactory.Meta):
        model = MailAccount

    name = factory.Sequence(lambda n: f"Mail Account {n}")
    imap_server = "imap.example.com"
    imap_port = 993
    imap_security = MailAccount.ImapSecurity.SSL
    username = factory.Sequence(lambda n: f"user{n}@example.com")
    password = "password"
    character_set = "UTF-8"
    account_type = MailAccount.MailAccountType.IMAP
    is_token = False


class MailRuleFactory(DjangoModelFactory[MailRule]):
    class Meta(DjangoModelFactory.Meta):
        model = MailRule

    name = factory.Sequence(lambda n: f"Mail Rule {n}")
    account = factory.SubFactory(MailAccountFactory)
    enabled = True
    folder = "INBOX"
    order = 0
    maximum_age = 30
    attachment_type = MailRule.AttachmentProcessing.ATTACHMENTS_ONLY
    consumption_scope = MailRule.ConsumptionScope.ATTACHMENTS_ONLY
    pdf_layout = MailRule.PdfLayout.DEFAULT
    action = MailRule.MailAction.MARK_READ
    assign_title_from = MailRule.TitleSource.FROM_SUBJECT
    assign_correspondent_from = MailRule.CorrespondentSource.FROM_NOTHING
    assign_owner_from_rule = True
    stop_processing = False


class ProcessedMailFactory(DjangoModelFactory[ProcessedMail]):
    class Meta(DjangoModelFactory.Meta):
        model = ProcessedMail

    rule = factory.SubFactory(MailRuleFactory)
    folder = "INBOX"
    uid = factory.Sequence(lambda n: str(n))
    subject = factory.Faker("sentence", nb_words=4)
    received = factory.LazyFunction(timezone.now)
    processed = factory.LazyFunction(timezone.now)
    status = "SUCCESS"
