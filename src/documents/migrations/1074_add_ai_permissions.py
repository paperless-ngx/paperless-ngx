# Generated migration for adding AI-related custom permissions

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1073_migrate_workflow_title_jinja"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="document",
            options={
                "ordering": ("-created",),
                "permissions": [
                    ("can_view_ai_suggestions", "Can view AI suggestions"),
                    ("can_apply_ai_suggestions", "Can apply AI suggestions"),
                    ("can_approve_deletions", "Can approve AI-recommended deletions"),
                    ("can_configure_ai", "Can configure AI settings"),
                ],
                "verbose_name": "document",
                "verbose_name_plural": "documents",
            },
        ),
    ]
