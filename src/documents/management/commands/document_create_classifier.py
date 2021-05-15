from django.core.management.base import BaseCommand

from ...tasks import train_classifier


class Command(BaseCommand):

    help = """
        Trains the classifier on your data and saves the resulting models to a
        file. The document consumer will then automatically use this new model.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
        train_classifier()
