import logging
from django.core.management.base import BaseCommand
from documents.sanity_checker import check_sanity, SanityError, SanityWarning

logger = logging.getLogger("paperless.management.sanity_checker")


class Command(BaseCommand):

    help = """
        This command checks your document archive for issues.
    """.replace("    ", "")

    def handle(self, *args, **options):

        messages = check_sanity(progress=True)

        if len(messages) == 0:
            logger.info("No issues found.")
        else:
            for msg in messages:
                if type(msg) == SanityError:
                    logger.error(str(msg))
                elif type(msg) == SanityWarning:
                    logger.warning(str(msg))
                else:
                    logger.info((str(msg)))
