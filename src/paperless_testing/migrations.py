from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

if TYPE_CHECKING:
    from django.apps.registry import Apps


class TestMigrations(TransactionTestCase):
    @property
    def app(self) -> str:
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from: Any = None
    dependencies: list[tuple[str, str]] | None = None
    migrate_to: Any = None

    def setUp(self) -> None:
        super().setUp()

        assert self.migrate_from and self.migrate_to, (
            f"TestCase '{type(self).__name__}' must define migrate_from and migrate_to properties"
        )
        self.migrate_from = [(self.app, self.migrate_from)]
        if self.dependencies is not None:
            self.migrate_from.extend(self.dependencies)
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        self.apps = old_apps

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps: Apps) -> None:
        pass

    def tearDown(self) -> None:
        """
        Ensure the database schema is restored to the latest migration after
        each migration test, so subsequent tests run against HEAD.
        """
        try:
            executor = MigrationExecutor(connection)
            executor.loader.build_graph()
            targets = executor.loader.graph.leaf_nodes()
            executor.migrate(targets)
        finally:
            super().tearDown()
