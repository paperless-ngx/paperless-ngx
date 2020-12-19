from django.db import models

import documents.models as document_models


class MailAccount(models.Model):

    IMAP_SECURITY_NONE = 1
    IMAP_SECURITY_SSL = 2
    IMAP_SECURITY_STARTTLS = 3

    IMAP_SECURITY_OPTIONS = (
        (IMAP_SECURITY_NONE, "No encryption"),
        (IMAP_SECURITY_SSL, "Use SSL"),
        (IMAP_SECURITY_STARTTLS, "Use STARTTLS"),
    )

    name = models.CharField(max_length=256, unique=True)

    imap_server = models.CharField(max_length=256)

    imap_port = models.IntegerField(
        blank=True,
        null=True,
        help_text="This is usually 143 for unencrypted and STARTTLS "
                  "connections, and 993 for SSL connections.")

    imap_security = models.PositiveIntegerField(
        choices=IMAP_SECURITY_OPTIONS,
        default=IMAP_SECURITY_SSL
    )

    username = models.CharField(max_length=256)

    password = models.CharField(max_length=256)

    def __str__(self):
        return self.name


class MailRule(models.Model):

    ACTION_DELETE = 1
    ACTION_MOVE = 2
    ACTION_MARK_READ = 3
    ACTION_FLAG = 4

    ACTIONS = (
        (ACTION_MARK_READ, "Mark as read, don't process read mails"),
        (ACTION_FLAG, "Flag the mail, don't process flagged mails"),
        (ACTION_MOVE, "Move to specified folder"),
        (ACTION_DELETE, "Delete"),
    )

    TITLE_FROM_SUBJECT = 1
    TITLE_FROM_FILENAME = 2

    TITLE_SELECTOR = (
        (TITLE_FROM_SUBJECT, "Use subject as title"),
        (TITLE_FROM_FILENAME, "Use attachment filename as title")
    )

    CORRESPONDENT_FROM_NOTHING = 1
    CORRESPONDENT_FROM_EMAIL = 2
    CORRESPONDENT_FROM_NAME = 3
    CORRESPONDENT_FROM_CUSTOM = 4

    CORRESPONDENT_SELECTOR = (
        (CORRESPONDENT_FROM_NOTHING,
         "Do not assign a correspondent"),
        (CORRESPONDENT_FROM_EMAIL,
         "Use mail address"),
        (CORRESPONDENT_FROM_NAME,
         "Use name (or mail address if not available)"),
        (CORRESPONDENT_FROM_CUSTOM,
         "Use correspondent selected below")
    )

    name = models.CharField(max_length=256, unique=True)

    order = models.IntegerField(default=0)

    account = models.ForeignKey(
        MailAccount,
        related_name="rules",
        on_delete=models.CASCADE
    )

    folder = models.CharField(default='INBOX', max_length=256)

    filter_from = models.CharField(max_length=256, null=True, blank=True)
    filter_subject = models.CharField(max_length=256, null=True, blank=True)
    filter_body = models.CharField(max_length=256, null=True, blank=True)

    maximum_age = models.PositiveIntegerField(
        default=30,
        help_text="Specified in days.")

    action = models.PositiveIntegerField(
        choices=ACTIONS,
        default=ACTION_MARK_READ,
    )

    action_parameter = models.CharField(
        max_length=256, blank=True, null=True,
        help_text="Additional parameter for the action selected above, i.e., "
                  "the target folder of the move to folder action."
    )

    assign_title_from = models.PositiveIntegerField(
        choices=TITLE_SELECTOR,
        default=TITLE_FROM_SUBJECT
    )

    assign_tag = models.ForeignKey(
        document_models.Tag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    assign_document_type = models.ForeignKey(
        document_models.DocumentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    assign_correspondent_from = models.PositiveIntegerField(
        choices=CORRESPONDENT_SELECTOR,
        default=CORRESPONDENT_FROM_NOTHING
    )

    assign_correspondent = models.ForeignKey(
        document_models.Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    def __str__(self):
        return f"{self.account.name}.{self.name}"
