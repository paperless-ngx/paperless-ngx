# Generated by Django 4.2.9 on 2024-01-12 05:33

import django.core.validators
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationconfiguration",
            name="app_logo",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="logo/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["jpg", "png", "gif", "svg"],
                    ),
                ],
                verbose_name="Application logo",
            ),
        ),
        migrations.AddField(
            model_name="applicationconfiguration",
            name="app_title",
            field=models.CharField(
                blank=True,
                max_length=48,
                null=True,
                verbose_name="Application title",
            ),
        ),
    ]
