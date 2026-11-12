import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0028_replace_tag_tree_fields"),
        ("paperless_mail", "0004_processedmail_uid_validity"),
    ]

    operations = [
        migrations.AddField(
            model_name="mailrule",
            name="assign_document_link_field",
            field=models.ForeignKey(
                blank=True,
                help_text="Use this Document Link custom field to link documents imported "
                "from the same email. Files remain separate.",
                limit_choices_to={"data_type": "documentlink"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="documents.customfield",
                verbose_name="link documents from the same email",
            ),
        ),
    ]
