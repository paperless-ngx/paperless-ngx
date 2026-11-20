import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0030_note_format"),
        ("paperless_mail", "0004_processedmail_uid_validity"),
    ]

    operations = [
        migrations.AddField(
            model_name="mailrule",
            name="same_email_link_field",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"data_type": "documentlink"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="documents.customfield",
                verbose_name="same email link field",
            ),
        ),
    ]
