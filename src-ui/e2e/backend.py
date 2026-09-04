"""Start a disposable Paperless instance for the Playwright test suite."""

# ruff: noqa: INP001, T201

from __future__ import annotations

import datetime
import logging
import logging.config
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def configure_environment(instance_root: Path) -> None:
    paths = {
        "PAPERLESS_CONSUMPTION_DIR": instance_root / "consume",
        "PAPERLESS_DATA_DIR": instance_root / "data",
        "PAPERLESS_MEDIA_ROOT": instance_root / "media",
        "PAPERLESS_SCRATCH_DIR": instance_root / "scratch",
    }
    for name, path in paths.items():
        path.mkdir(parents=True)
        os.environ[name] = str(path)
    (paths["PAPERLESS_DATA_DIR"] / "index").mkdir()

    os.environ.update(
        {
            "DJANGO_SETTINGS_MODULE": "paperless.settings",
            "PAPERLESS_AI_ENABLED": "false",
            "PAPERLESS_CHANNELS_BACKEND": "channels.layers.InMemoryChannelLayer",
            "PAPERLESS_DEBUG": "true",
            "PAPERLESS_SECRET_KEY": "playwright-only-not-a-real-secret",
        },
    )
    sys.path.insert(0, str(SOURCE_ROOT))


def seed_database() -> None:
    from django.contrib.auth.models import User
    from django.core.management import call_command
    from django.utils import timezone

    from documents.models import Correspondent
    from documents.models import CustomField
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import Note
    from documents.models import SavedView
    from documents.models import SavedViewFilterRule
    from documents.models import StoragePath
    from documents.models import Tag
    from documents.models import UiSettings

    # Fixed credentials are safe within this disposable, localhost-only instance.
    admin = User.objects.create_superuser(
        username="playwright",
        password="playwright",  # NOSONAR
    )
    User.objects.create_user(
        username="viewer",
        password="viewer",  # NOSONAR
    )

    inbox = Tag.objects.create(name="Inbox", is_inbox_tag=True, owner=admin)
    quick_filter = Tag.objects.create(name="Another Sample Tag", owner=admin)
    Tag.objects.create(name="TagWithPartial", owner=admin)
    invoice = DocumentType.objects.create(name="Invoice Test", owner=admin)
    correspondent_1 = Correspondent.objects.create(
        name="Test Correspondent 1",
        owner=admin,
    )
    correspondent_2 = Correspondent.objects.create(name="Correspondent 9", owner=admin)
    storage_path = StoragePath.objects.create(
        name="Testing 12",
        path="e2e/{created_year}/{title}",
        owner=admin,
    )
    CustomField.objects.create(
        name="Test Select Field",
        data_type=CustomField.FieldDataType.SELECT,
        extra_data={
            "select_options": [
                {"id": "abc123", "label": "Alpha"},
                {"id": "def456", "label": "Beta"},
            ],
        },
    )

    today = timezone.localdate()
    documents = []
    for number in range(1, 62):
        title = f"test document {number}" if number <= 9 else f"document {number}"
        content = (
            f"Playwright test content for document {number}"
            if number <= 32
            else f"Seeded content for document {number}"
        )
        created = today if number == 1 else datetime.date(2021, 1, 1)
        if number in (2, 3):
            created = datetime.date(2022, 12, 11)

        documents.append(
            Document(
                title=title,
                content=content,
                checksum=f"{number:064x}",
                mime_type="application/pdf",
                filename=f"{number:07}.pdf",
                original_filename=f"document-{number}.pdf",
                archive_serial_number=1122 + number if number <= 6 else None,
                created=created,
                owner=admin,
                document_type=invoice if number <= 3 else None,
                correspondent=(
                    correspondent_1
                    if number <= 4
                    else correspondent_2
                    if number <= 7
                    else None
                ),
                storage_path=storage_path if number <= 8 else None,
            ),
        )

    Document.objects.bulk_create(documents)
    originals = Path(os.environ["PAPERLESS_MEDIA_ROOT"]) / "documents" / "originals"
    originals.mkdir(parents=True)
    thumbnails = Path(os.environ["PAPERLESS_MEDIA_ROOT"]) / "documents" / "thumbnails"
    thumbnails.mkdir(parents=True)
    sample_pdf = SOURCE_ROOT / "documents" / "tests" / "samples" / "simple.pdf"
    for document in documents:
        shutil.copyfile(sample_pdf, originals / document.filename)
        shutil.copyfile(
            SOURCE_ROOT / "documents" / "resources" / "document.webp",
            thumbnails / f"{document.pk:07}.webp",
        )

    for document in documents[:8]:
        document.tags.add(inbox)
    documents[0].tags.add(quick_filter)

    for number in range(1, 5):
        Note.objects.create(
            note=f"Playwright note {number}",
            document=documents[0],
            user=admin,
        )

    inbox_view = SavedView.objects.create(
        name="Inbox",
        owner=admin,
        sort_field="created",
        sort_reverse=True,
        page_size=10,
        display_mode=SavedView.DisplayMode.TABLE,
        display_fields=["created", "title", "tag", "documenttype"],
    )
    SavedViewFilterRule.objects.create(
        saved_view=inbox_view,
        rule_type=6,
        value=str(inbox.pk),
    )

    UiSettings.objects.create(
        user=admin,
        settings={
            "language": "",
            "bulk_edit": {"confirmation_dialogs": True, "apply_on_close": False},
            "documentListSize": 50,
            "dark_mode": {
                "use_system": True,
                "enabled": False,
                "thumb_inverted": True,
            },
            "theme": {"color": "#9fbf2f"},
            "document_details": {"native_pdf_viewer": False},
            "date_display": {"date_locale": "", "date_format": "mediumDate"},
            "comments_enabled": True,
            "slim_sidebar": False,
            "update_checking": {"enabled": False},
            "saved_views": {
                "warn_on_unsaved_change": True,
                "dashboard_views_visible_ids": [inbox_view.pk],
                "sidebar_views_visible_ids": [inbox_view.pk],
            },
            "notes_enabled": True,
            "tour_complete": True,
        },
    )

    call_command(
        "document_index",
        "reindex",
        recreate=True,
        heap_size_mb=16,
        verbosity=0,
    )


def main() -> None:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="paperless-playwright-") as instance:
        configure_environment(Path(instance))

        os.chdir(SOURCE_ROOT)
        print("Loading the Paperless backend...", flush=True)
        import django

        django.setup()

        from django.conf import settings
        from django.core.management import call_command

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True

        print("Migrating the disposable database...", flush=True)
        call_command("migrate", interactive=False, verbosity=0)
        print("Seeding Playwright data...", flush=True)
        seed_database()
        elapsed = time.monotonic() - started
        print(f"Playwright backend ready in {elapsed:.1f}s", flush=True)
        settings.LOGGING["handlers"]["console"]["level"] = "WARNING"
        settings.LOGGING["handlers"]["playwright_null"] = {
            "class": "logging.NullHandler",
        }
        settings.LOGGING["loggers"]["django.server"] = {
            "handlers": ["playwright_null"],
            "propagate": False,
        }
        logging.config.dictConfig(settings.LOGGING)
        call_command(
            "runserver",
            "localhost:8001",
            use_reloader=False,
            verbosity=1,
        )


if __name__ == "__main__":
    main()
