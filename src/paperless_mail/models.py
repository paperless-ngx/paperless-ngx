from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import documents.models as document_models


class MailAccount(document_models.ModelWithOwner):
    class Meta:
        verbose_name = _("mail account")
        verbose_name_plural = _("mail accounts")

    class ImapSecurity(models.IntegerChoices):
        NONE = 1, _("No encryption")
        SSL = 2, _("Use SSL")
        STARTTLS = 3, _("Use STARTTLS")

    class MailAccountType(models.IntegerChoices):
        IMAP = 1, _("IMAP")
        GMAIL_OAUTH = 2, _("Gmail OAuth")
        OUTLOOK_OAUTH = 3, _("Outlook OAuth")

    name = models.CharField(_("name"), max_length=256, unique=True)

    imap_server = models.CharField(_("IMAP server"), max_length=256)

    imap_port = models.IntegerField(
        _("IMAP port"),
        blank=True,
        null=True,
        help_text=_(
            "This is usually 143 for unencrypted and STARTTLS "
            "connections, and 993 for SSL connections.",
        ),
    )

    imap_security = models.PositiveIntegerField(
        _("IMAP security"),
        choices=ImapSecurity.choices,
        default=ImapSecurity.SSL,
    )

    username = models.CharField(_("username"), max_length=256)

    password = models.TextField(_("password"))

    is_token = models.BooleanField(_("Is token authentication"), default=False)

    character_set = models.CharField(
        _("character set"),
        max_length=256,
        default="UTF-8",
        help_text=_(
            "The character set to use when communicating with the "
            "mail server, such as 'UTF-8' or 'US-ASCII'.",
        ),
    )

    account_type = models.PositiveIntegerField(
        _("account type"),
        choices=MailAccountType.choices,
        default=MailAccountType.IMAP,
    )

    refresh_token = models.TextField(
        _("refresh token"),
        blank=True,
        null=True,
        help_text=_(
            "The refresh token to use for token authentication e.g. with oauth2.",
        ),
    )

    expiration = models.DateTimeField(
        _("expiration"),
        blank=True,
        null=True,
        help_text=_(
            "The expiration date of the refresh token. ",
        ),
    )

    def __str__(self):
        return self.name


class MailRule(document_models.ModelWithOwner):
    class Meta:
        verbose_name = _("mail rule")
        verbose_name_plural = _("mail rules")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "owner"],
                name="%(app_label)s_%(class)s_unique_name_owner",
            ),
            models.UniqueConstraint(
                name="%(app_label)s_%(class)s_name_unique",
                fields=["name"],
                condition=models.Q(owner__isnull=True),
            ),
        ]

    class ConsumptionScope(models.IntegerChoices):
        ATTACHMENTS_ONLY = 1, _("Only process attachments.")
        EML_ONLY = 2, _("Process full Mail (with embedded attachments in file) as .eml")
        EVERYTHING = (
            3,
            _(
                "Process full Mail (with embedded attachments in file) as .eml "
                "+ process attachments as separate documents",
            ),
        )

    class AttachmentProcessing(models.IntegerChoices):
        ATTACHMENTS_ONLY = 1, _("Only process attachments.")
        EVERYTHING = 2, _("Process all files, including 'inline' attachments.")

    class MailAction(models.IntegerChoices):
        DELETE = 1, _("Delete")
        MOVE = 2, _("Move to specified folder")
        MARK_READ = 3, _("Mark as read, don't process read mails")
        FLAG = 4, _("Flag the mail, don't process flagged mails")
        TAG = 5, _("Tag the mail with specified tag, don't process tagged mails")

    class TitleSource(models.IntegerChoices):
        FROM_SUBJECT = 1, _("Use subject as title")
        FROM_FILENAME = 2, _("Use attachment filename as title")
        NONE = 3, _("Do not assign title from rule")

    class CorrespondentSource(models.IntegerChoices):
        FROM_NOTHING = 1, _("Do not assign a correspondent")
        FROM_EMAIL = 2, _("Use mail address")
        FROM_NAME = 3, _("Use name (or mail address if not available)")
        FROM_CUSTOM = 4, _("Use correspondent selected below")

    name = models.CharField(_("name"), max_length=256)

    order = models.IntegerField(_("order"), default=0)

    account = models.ForeignKey(
        MailAccount,
        related_name="rules",
        on_delete=models.CASCADE,
        verbose_name=_("account"),
    )

    enabled = models.BooleanField(_("enabled"), default=True)

    folder = models.CharField(
        _("folder"),
        default="INBOX",
        max_length=256,
        help_text=_(
            "Subfolders must be separated by a delimiter, often a dot ('.') or"
            " slash ('/'), but it varies by mail server.",
        ),
    )

    filter_from = models.CharField(
        _("filter from"),
        max_length=256,
        null=True,
        blank=True,
    )

    filter_to = models.CharField(
        _("filter to"),
        max_length=256,
        null=True,
        blank=True,
    )

    filter_subject = models.CharField(
        _("filter subject"),
        max_length=256,
        null=True,
        blank=True,
    )

    filter_body = models.CharField(
        _("filter body"),
        max_length=256,
        null=True,
        blank=True,
    )

    filter_attachment_filename_include = models.CharField(
        _("filter attachment filename inclusive"),
        max_length=256,
        null=True,
        blank=True,
        help_text=_(
            "Only consume documents which entirely match this "
            "filename if specified. Wildcards such as *.pdf or "
            "*invoice* are allowed. Case insensitive.",
        ),
    )

    filter_attachment_filename_exclude = models.CharField(
        _("filter attachment filename exclusive"),
        max_length=256,
        null=True,
        blank=True,
        help_text=_(
            "Do not consume documents which entirely match this "
            "filename if specified. Wildcards such as *.pdf or "
            "*invoice* are allowed. Case insensitive.",
        ),
    )

    maximum_age = models.PositiveIntegerField(
        _("maximum age"),
        default=30,
        help_text=_("Specified in days."),
    )

    attachment_type = models.PositiveIntegerField(
        _("attachment type"),
        choices=AttachmentProcessing.choices,
        default=AttachmentProcessing.ATTACHMENTS_ONLY,
        help_text=_(
            "Inline attachments include embedded images, so it's best "
            "to combine this option with a filename filter.",
        ),
    )

    consumption_scope = models.PositiveIntegerField(
        _("consumption scope"),
        choices=ConsumptionScope.choices,
        default=ConsumptionScope.ATTACHMENTS_ONLY,
    )

    action = models.PositiveIntegerField(
        _("action"),
        choices=MailAction.choices,
        default=MailAction.MARK_READ,
    )

    action_parameter = models.CharField(
        _("action parameter"),
        max_length=256,
        blank=True,
        null=True,
        help_text=_(
            "Additional parameter for the action selected above, "
            "i.e., "
            "the target folder of the move to folder action. "
            "Subfolders must be separated by dots.",
        ),
    )

    assign_title_from = models.PositiveIntegerField(
        _("assign title from"),
        choices=TitleSource.choices,
        default=TitleSource.FROM_SUBJECT,
    )

    assign_tags = models.ManyToManyField(
        document_models.Tag,
        blank=True,
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
        choices=CorrespondentSource.choices,
        default=CorrespondentSource.FROM_NOTHING,
    )

    assign_correspondent = models.ForeignKey(
        document_models.Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("assign this correspondent"),
    )

    assign_owner_from_rule = models.BooleanField(
        _("Assign the rule owner to documents"),
        default=True,
    )

    def __str__(self):
        return f"{self.account.name}.{self.name}"


class ProcessedMail(document_models.ModelWithOwner):
    rule = models.ForeignKey(
        MailRule,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        editable=False,
    )

    folder = models.CharField(
        _("folder"),
        null=False,
        blank=False,
        max_length=256,
        editable=False,
    )

    uid = models.CharField(
        _("uid"),
        null=False,
        blank=False,
        max_length=256,
        editable=False,
    )

    subject = models.CharField(
        _("subject"),
        null=False,
        blank=False,
        max_length=256,
        editable=False,
    )

    received = models.DateTimeField(
        _("received"),
        null=False,
        blank=False,
        editable=False,
    )

    processed = models.DateTimeField(
        _("processed"),
        default=timezone.now,
        editable=False,
    )

    status = models.CharField(
        _("status"),
        null=False,
        blank=False,
        max_length=256,
        editable=False,
    )

    error = models.TextField(
        _("error"),
        null=True,
        blank=True,
        editable=False,
    )
