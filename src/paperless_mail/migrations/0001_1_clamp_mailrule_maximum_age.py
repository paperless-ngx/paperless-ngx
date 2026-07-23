# Split out of 0002_optimize_integer_field_sizes.py into its own migration
# (own transaction). Running this UPDATE in the same transaction as the
# later ALTER TABLE on paperless_mail_mailrule can fail on PostgreSQL with
# "cannot ALTER TABLE because it has pending trigger events", since the
# update queues FK trigger events against that table that are still pending
# when the subsequent AlterField tries to rewrite it. Committing the clamp
# here first avoids that.
from django.db import migrations


def clamp_mailrule_maximum_age(apps, schema_editor):
    # Clamp the maximum_age field of MailRule because of PositiveIntegerField --> PositiveSmallIntegerField
    MailRule = apps.get_model("paperless_mail", "MailRule")
    MailRule.objects.filter(maximum_age__gt=32767).update(maximum_age=32767)


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0001_squashed"),
    ]

    operations = [
        migrations.RunPython(
            clamp_mailrule_maximum_age,
            migrations.RunPython.noop,
        ),
    ]
