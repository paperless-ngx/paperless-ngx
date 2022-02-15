from django.db import models

import documents.models as document_models

from django.utils.translation import gettext_lazy as _


class MailAccount(models.Model):

    class Meta:
        verbose_name = _("mail account")
        verbose_name_plural = _("mail accounts")

    IMAP_SECURITY_NONE = 1
    IMAP_SECURITY_SSL = 2
    IMAP_SECURITY_STARTTLS = 3

    IMAP_SECURITY_OPTIONS = (
        (IMAP_SECURITY_NONE, _("No encryption")),
        (IMAP_SECURITY_SSL, _("Use SSL")),
        (IMAP_SECURITY_STARTTLS, _("Use STARTTLS")),
    )

    name = models.CharField(
        _("name"),
        max_length=256, unique=True)

    imap_server = models.CharField(
        _("IMAP server"),
        max_length=256)

    imap_port = models.IntegerField(
        _("IMAP port"),
        blank=True,
        null=True,
        help_text=_("This is usually 143 for unencrypted and STARTTLS "
                    "connections, and 993 for SSL connections."))

    imap_security = models.PositiveIntegerField(
        _("IMAP security"),
        choices=IMAP_SECURITY_OPTIONS,
        default=IMAP_SECURITY_SSL
    )

    username = models.CharField(
        _("username"),
        max_length=256)

    password = models.CharField(
        _("password"),
        max_length=256)

    character_set = models.CharField(
        _("character set"),
        max_length=256,
        default="UTF-8",
        help_text=_("The character set to use when communicating with the "
                    "mail server, such as 'UTF-8' or 'US-ASCII'.")
    )

    def __str__(self):
        return self.name


class MailRule(models.Model):

    class Meta:
        verbose_name = _("mail rule")
        verbose_name_plural = _("mail rules")

    ATTACHMENT_TYPE_ATTACHMENTS_ONLY = 1
    ATTACHMENT_TYPE_EVERYTHING = 2

    ATTACHMENT_TYPES = (
        (ATTACHMENT_TYPE_ATTACHMENTS_ONLY, _("Only process attachments.")),
        (ATTACHMENT_TYPE_EVERYTHING, _("Process all files, including 'inline' "
                                       "attachments."))
    )

    ACTION_DELETE = 1
    ACTION_MOVE = 2
    ACTION_MARK_READ = 3
    ACTION_FLAG = 4

    ACTIONS = (
        (ACTION_MARK_READ, _("Mark as read, don't process read mails")),
        (ACTION_FLAG, _("Flag the mail, don't process flagged mails")),
        (ACTION_MOVE, _("Move to specified folder")),
        (ACTION_DELETE, _("Delete")),
    )

    TITLE_FROM_SUBJECT = 1
    TITLE_FROM_FILENAME = 2

    TITLE_SELECTOR = (
        (TITLE_FROM_SUBJECT, _("Use subject as title")),
        (TITLE_FROM_FILENAME, _("Use attachment filename as title"))
    )

    CORRESPONDENT_FROM_NOTHING = 1
    CORRESPONDENT_FROM_EMAIL = 2
    CORRESPONDENT_FROM_NAME = 3
    CORRESPONDENT_FROM_CUSTOM = 4

    CORRESPONDENT_SELECTOR = (
        (CORRESPONDENT_FROM_NOTHING,
         _("Do not assign a correspondent")),
        (CORRESPONDENT_FROM_EMAIL,
         _("Use mail address")),
        (CORRESPONDENT_FROM_NAME,
         _("Use name (or mail address if not available)")),
        (CORRESPONDENT_FROM_CUSTOM,
         _("Use correspondent selected below"))
    )

    name = models.CharField(
        _("name"),
        max_length=256, unique=True)

    order = models.IntegerField(
        _("order"),
        default=0)

    account = models.ForeignKey(
        MailAccount,
        related_name="rules",
        on_delete=models.CASCADE,
        verbose_name=_("account")
    )

    folder = models.CharField(
        _("folder"),
        default='INBOX', max_length=256,
        help_text=_("Subfolders must be separated by dots.")
    )

    filter_from = models.CharField(
        _("filter from"),
        max_length=256, null=True, blank=True)
    filter_subject = models.CharField(
        _("filter subject"),
        max_length=256, null=True, blank=True)
    filter_body = models.CharField(
        _("filter body"),
        max_length=256, null=True, blank=True)

    filter_attachment_filename = models.CharField(
        _("filter attachment filename"),
        max_length=256, null=True, blank=True,
        help_text=_("Only consume documents which entirely match this "
                    "filename if specified. Wildcards such as *.pdf or "
                    "*invoice* are allowed. Case insensitive.")
    )

    maximum_age = models.PositiveIntegerField(
        _("maximum age"),
        default=30,
        help_text=_("Specified in days."))

    attachment_type = models.PositiveIntegerField(
        _("attachment type"),
        choices=ATTACHMENT_TYPES,
        default=ATTACHMENT_TYPE_ATTACHMENTS_ONLY,
        help_text=_("Inline attachments include embedded images, so it's best "
                    "to combine this option with a filename filter.")
    )

    action = models.PositiveIntegerField(
        _("action"),
        choices=ACTIONS,
        default=ACTION_MARK_READ,
    )

    action_parameter = models.CharField(
        _("action parameter"),
        max_length=256, blank=True, null=True,
        help_text=_("Additional parameter for the action selected above, "
                    "i.e., "
                    "the target folder of the move to folder action. "
                    "Subfolders must be separated by dots.")
    )

    assign_title_from = models.PositiveIntegerField(
        _("assign title from"),
        choices=TITLE_SELECTOR,
        default=TITLE_FROM_SUBJECT
    )

    assign_tag = models.ForeignKey(
        document_models.Tag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("assign this tag"),
    )

    assign_document_type = models.ForeignKey(
        document_models.DocumentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("assign this document type"),
    )

    assign_correspondent_from = models.PositiveIntegerField(
        _("assign correspondent from"),
        choices=CORRESPONDENT_SELECTOR,
        default=CORRESPONDENT_FROM_NOTHING
    )

    assign_correspondent = models.ForeignKey(
        document_models.Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("assign this correspondent")
    )

    def __str__(self):
        return f"{self.account.name}.{self.name}"
