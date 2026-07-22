import re

from django.db import migrations

# Matches "note:" when NOT preceded by a word character or dot.
# This avoids false positives like "denote:" or already-migrated "notes.note:".
# Handles start-of-string, whitespace, parentheses, +/- operators per Whoosh syntax.
_NOTE_RE = re.compile(r"(?<![.\w])note:")

# Same logic for "custom_field:" -> "custom_fields.value:"
_CUSTOM_FIELD_RE = re.compile(r"(?<![.\w])custom_field:")


def migrate_fulltext_query_field_prefixes(apps, schema_editor):
    SavedViewFilterRule = apps.get_model("documents", "SavedViewFilterRule")

    # rule_type 20 = "fulltext query" — value is a search query string
    for rule in SavedViewFilterRule.objects.filter(rule_type=20).exclude(
        value__isnull=True,
    ):
        new_value = _NOTE_RE.sub("notes.note:", rule.value)
        new_value = _CUSTOM_FIELD_RE.sub("custom_fields.value:", new_value)

        if new_value != rule.value:
            rule.value = new_value
            rule.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_sha256_checksums"),
    ]

    operations = [
        migrations.RunPython(
            migrate_fulltext_query_field_prefixes,
            migrations.RunPython.noop,
        ),
    ]
