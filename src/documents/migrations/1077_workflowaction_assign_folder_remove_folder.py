import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1076_add_folder_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowaction",
            name="assign_folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="documents.folder",
                verbose_name="assign this folder",
            ),
        ),
        migrations.AddField(
            model_name="workflowaction",
            name="remove_folder",
            field=models.BooleanField(default=False, verbose_name="remove folder"),
        ),
    ]
