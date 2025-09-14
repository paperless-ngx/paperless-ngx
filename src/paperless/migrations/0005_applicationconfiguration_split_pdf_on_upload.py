from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0004_applicationconfiguration_barcode_asn_prefix_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationconfiguration",
            name="split_pdf_on_upload",
            field=models.BooleanField(null=True, verbose_name="Split PDFs on upload"),
        ),
    ]
