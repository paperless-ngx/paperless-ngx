import os
from argparse import ArgumentParser

from django.core.management import CommandError


class MultiProcessMixin:
    """
    Small class to handle adding an argument and validating it
    for the use of multiple processes
    """

    def add_argument_processes_mixin(self, parser: ArgumentParser):
        parser.add_argument(
            "--processes",
            default=max(1, os.cpu_count() // 4),
            type=int,
            help="Number of processes to distribute work amongst",
        )

    def handle_processes_mixin(self, *args, **options):
        self.process_count = options["processes"]
        if self.process_count < 1:
            raise CommandError("There must be at least 1 process")


class ProgressBarMixin:
    """
    Many commands use a progress bar, which can be disabled
    via this class
    """

    def add_argument_progress_bar_mixin(self, parser: ArgumentParser):
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def handle_progress_bar_mixin(self, *args, **options):
        self.no_progress_bar = options["no_progress_bar"]
        self.use_progress_bar = not self.no_progress_bar
