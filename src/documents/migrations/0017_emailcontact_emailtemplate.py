import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("documents", "0016_sha256_checksums"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailContact",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=256,
                        verbose_name="name",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=254,
                        verbose_name="email address",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="email_contacts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="owner",
                    ),
                ),
            ],
            options={
                "verbose_name": "email contact",
                "verbose_name_plural": "email contacts",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="EmailTemplate",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=256,
                        verbose_name="name",
                    ),
                ),
                (
                    "subject",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=512,
                        verbose_name="subject",
                    ),
                ),
                (
                    "body",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="body",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="email_templates",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="owner",
                    ),
                ),
            ],
            options={
                "verbose_name": "email template",
                "verbose_name_plural": "email templates",
                "ordering": ("name",),
            },
        ),
    ]
