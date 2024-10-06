from rest_framework import serializers

from documents.serialisers import CorrespondentField
from documents.serialisers import DocumentTypeField
from documents.serialisers import OwnedObjectSerializer
from documents.serialisers import TagsField
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class ObfuscatedPasswordField(serializers.Field):
    """
    Sends *** string instead of password in the clear
    """

    def to_representation(self, value):
        return "*" * len(value)

    def to_internal_value(self, data):
        return data


class MailAccountSerializer(OwnedObjectSerializer):
    password = ObfuscatedPasswordField()

    class Meta:
        model = MailAccount
        fields = [
            "id",
            "name",
            "imap_server",
            "imap_port",
            "imap_security",
            "username",
            "password",
            "character_set",
            "is_token",
            "owner",
            "user_can_change",
            "permissions",
            "set_permissions",
            "account_type",
            "expiration",
        ]

    def update(self, instance, validated_data):
        if (
            "password" in validated_data
            and len(validated_data.get("password").replace("*", "")) == 0
        ):
            validated_data.pop("password")
        super().update(instance, validated_data)
        return instance


class AccountField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return MailAccount.objects.all().order_by("-id")


class MailRuleSerializer(OwnedObjectSerializer):
    account = AccountField(required=True)
    action_parameter = serializers.CharField(
        allow_null=True,
        required=False,
        default="",
    )
    assign_correspondent = CorrespondentField(allow_null=True, required=False)
    assign_tags = TagsField(many=True, allow_null=True, required=False)
    assign_document_type = DocumentTypeField(allow_null=True, required=False)
    order = serializers.IntegerField(required=False)

    class Meta:
        model = MailRule
        fields = [
            "id",
            "name",
            "account",
            "enabled",
            "folder",
            "filter_from",
            "filter_to",
            "filter_subject",
            "filter_body",
            "filter_attachment_filename_include",
            "filter_attachment_filename_exclude",
            "maximum_age",
            "action",
            "action_parameter",
            "assign_title_from",
            "assign_tags",
            "assign_correspondent_from",
            "assign_correspondent",
            "assign_document_type",
            "assign_owner_from_rule",
            "order",
            "attachment_type",
            "consumption_scope",
            "owner",
            "user_can_change",
            "permissions",
            "set_permissions",
        ]

    def update(self, instance, validated_data):
        super().update(instance, validated_data)
        return instance

    def create(self, validated_data):
        if "assign_tags" in validated_data:
            assign_tags = validated_data.pop("assign_tags")
        mail_rule = super().create(validated_data)
        if assign_tags:
            mail_rule.assign_tags.set(assign_tags)
        return mail_rule

    def validate(self, attrs):
        if (
            attrs["action"] == MailRule.MailAction.TAG
            or attrs["action"] == MailRule.MailAction.MOVE
        ) and attrs["action_parameter"] is None:
            raise serializers.ValidationError("An action parameter is required.")

        return attrs
