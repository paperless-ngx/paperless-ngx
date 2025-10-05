# Generated manually for adding custom field filtering to WorkflowTrigger

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1072_workflowtrigger_filter_tags_require_all"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowtrigger",
            name="filter_has_custom_fields",
            field=models.ManyToManyField(
                blank=True,
                related_name="+",
                to="documents.customfield",
                verbose_name="has these custom fields",
            ),
        ),
        migrations.AddField(
            model_name="workflowtrigger",
            name="filter_custom_fields_values",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Values to match against the custom fields. Document must have custom field instances with these values.",
                null=True,
                verbose_name="custom field values",
            ),
        ),
    ]
