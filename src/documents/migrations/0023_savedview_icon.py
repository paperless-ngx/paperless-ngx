from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0022_add_perf_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedview",
            name="icon",
            field=models.CharField(
                choices=[
                    ("archive", "Archive"),
                    ("bell", "Bell"),
                    ("boxes", "Boxes"),
                    ("calendar", "Calendar"),
                    ("card-checklist", "Checklist"),
                    ("chat-left-text", "Chat"),
                    ("check-circle", "Check"),
                    ("clipboard", "Clipboard"),
                    ("clock-history", "Clock"),
                    ("download", "Download"),
                    ("envelope", "Envelope"),
                    ("exclamation-triangle", "Warning"),
                    ("file-earmark", "File"),
                    ("file-earmark-check", "Checked file"),
                    ("file-earmark-lock", "Locked file"),
                    ("file-text", "Text file"),
                    ("files", "Files"),
                    ("folder", "Folder"),
                    ("funnel", "Filter"),
                    ("gear", "Gear"),
                    ("hash", "Hash"),
                    ("house", "House"),
                    ("journals", "Journals"),
                    ("list-task", "Task list"),
                    ("people", "People"),
                    ("person", "Person"),
                    ("printer", "Printer"),
                    ("search", "Search"),
                    ("send", "Send"),
                    ("stack", "Stack"),
                    ("stars", "Stars"),
                    ("tag", "Tag"),
                    ("tags", "Tags"),
                    ("upc-scan", "Barcode"),
                ],
                default="funnel",
                max_length=64,
                verbose_name="icon",
            ),
        ),
    ]
