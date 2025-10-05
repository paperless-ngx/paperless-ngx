# Generated manually for adding filter_tags_require_all field to WorkflowTrigger

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1071_tag_tn_ancestors_count_tag_tn_ancestors_pks_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowtrigger",
            name="filter_tags_require_all",
            field=models.BooleanField(
                default=False,
                help_text="If checked, document must have ALL selected tags. If unchecked, document needs ANY of the selected tags.",
                verbose_name="require all tags",
            ),
        ),
    ]
