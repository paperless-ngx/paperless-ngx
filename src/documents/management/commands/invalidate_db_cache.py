from django.core.management.base import BaseCommand

from paperless.db_cache import CacheManager


class Command(BaseCommand):
    help = "This will clear the database read cache."

    def handle(self, *args, **options):
        verbosity = int(options["verbosity"])
        if verbosity > 0:
            self.stdout.write("Clearing cache...")

        try:
            deleted_keys = CacheManager().invalidate_cache()
            if verbosity > 0:
                self.stdout.write(
                    f"Database read cache successfully invalidated ({deleted_keys} keys deleted).",
                )

        except Exception as e:
            self.stdout.write("Error: Could not clear the cache.")
            raise e
