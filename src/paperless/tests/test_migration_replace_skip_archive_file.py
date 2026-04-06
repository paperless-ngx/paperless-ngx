from documents.tests.utils import TestMigrations


class TestMigrateSkipArchiveFile(TestMigrations):
    migrate_from = "0007_optimize_integer_field_sizes"
    migrate_to = "0008_replace_skip_archive_file"

    def setUpBeforeMigration(self, apps):
        ApplicationConfiguration = apps.get_model(
            "paperless",
            "ApplicationConfiguration",
        )
        ApplicationConfiguration.objects.all().delete()
        ApplicationConfiguration.objects.create(
            pk=1,
            mode="skip",
            skip_archive_file="always",
        )
        ApplicationConfiguration.objects.create(
            pk=2,
            mode="redo",
            skip_archive_file="with_text",
        )
        ApplicationConfiguration.objects.create(
            pk=3,
            mode="force",
            skip_archive_file="never",
        )
        ApplicationConfiguration.objects.create(
            pk=4,
            mode="skip_noarchive",
            skip_archive_file=None,
        )
        ApplicationConfiguration.objects.create(
            pk=5,
            mode="skip_noarchive",
            skip_archive_file="never",
        )
        ApplicationConfiguration.objects.create(pk=6, mode=None, skip_archive_file=None)

    def _get_config(self, pk):
        ApplicationConfiguration = self.apps.get_model(
            "paperless",
            "ApplicationConfiguration",
        )
        return ApplicationConfiguration.objects.get(pk=pk)

    def test_skip_mapped_to_auto(self):
        config = self._get_config(1)
        assert config.mode == "auto"

    def test_skip_archive_always_mapped_to_never(self):
        config = self._get_config(1)
        assert config.archive_file_generation == "never"

    def test_redo_unchanged(self):
        config = self._get_config(2)
        assert config.mode == "redo"

    def test_skip_archive_with_text_mapped_to_auto(self):
        config = self._get_config(2)
        assert config.archive_file_generation == "auto"

    def test_force_unchanged(self):
        config = self._get_config(3)
        assert config.mode == "force"

    def test_skip_archive_never_mapped_to_always(self):
        config = self._get_config(3)
        assert config.archive_file_generation == "always"

    def test_skip_noarchive_mapped_to_auto(self):
        config = self._get_config(4)
        assert config.mode == "auto"

    def test_skip_noarchive_implies_archive_never(self):
        config = self._get_config(4)
        assert config.archive_file_generation == "never"

    def test_skip_noarchive_explicit_skip_archive_takes_precedence(self):
        """skip_archive_file=never maps to always, not overridden by skip_noarchive."""
        config = self._get_config(5)
        assert config.mode == "auto"
        assert config.archive_file_generation == "always"

    def test_null_values_remain_null(self):
        config = self._get_config(6)
        assert config.mode is None
        assert config.archive_file_generation is None
