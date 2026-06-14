from django.db import migrations
from django.db import models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0022_folder_document_folder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="savedviewfilterrule",
            name="rule_type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, _("title contains")),
                    (1, _("content contains")),
                    (2, _("ASN is")),
                    (3, _("correspondent is")),
                    (4, _("document type is")),
                    (5, _("is in inbox")),
                    (6, _("has tag")),
                    (7, _("has any tag")),
                    (8, _("created before")),
                    (9, _("created after")),
                    (10, _("created year is")),
                    (11, _("created month is")),
                    (12, _("created day is")),
                    (13, _("added before")),
                    (14, _("added after")),
                    (15, _("modified before")),
                    (16, _("modified after")),
                    (17, _("does not have tag")),
                    (18, _("does not have ASN")),
                    (19, _("title or content contains")),
                    (20, _("fulltext query")),
                    (21, _("more like this")),
                    (22, _("has tags in")),
                    (23, _("ASN greater than")),
                    (24, _("ASN less than")),
                    (25, _("storage path is")),
                    (26, _("has correspondent in")),
                    (27, _("does not have correspondent in")),
                    (28, _("has document type in")),
                    (29, _("does not have document type in")),
                    (30, _("has storage path in")),
                    (31, _("does not have storage path in")),
                    (32, _("owner is")),
                    (33, _("has owner in")),
                    (34, _("does not have owner")),
                    (35, _("does not have owner in")),
                    (36, _("has custom field value")),
                    (37, _("is shared by me")),
                    (38, _("has custom fields")),
                    (39, _("has custom field in")),
                    (40, _("does not have custom field in")),
                    (41, _("does not have custom field")),
                    (42, _("custom fields query")),
                    (43, _("created to")),
                    (44, _("created from")),
                    (45, _("added to")),
                    (46, _("added from")),
                    (47, _("mime type is")),
                    (48, _("simple title search")),
                    (49, _("simple text search")),
                    (50, _("folder is")),
                    (51, _("has folder in")),
                    (52, _("does not have folder in")),
                ],
                verbose_name="rule type",
            ),
        ),
    ]
