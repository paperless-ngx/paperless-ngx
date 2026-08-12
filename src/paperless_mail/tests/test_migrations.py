import importlib

from django.db import migrations


def test_optimize_integer_fields_preserves_released_migration_history():
    migration_module = importlib.import_module(
        "paperless_mail.migrations.0002_optimize_integer_field_sizes",
    )

    assert migration_module.Migration.dependencies == [
        ("paperless_mail", "0001_squashed"),
    ]


def test_mailrule_maximum_age_is_clamped_before_non_atomic_alter():
    migration_module = importlib.import_module(
        "paperless_mail.migrations.0002_optimize_integer_field_sizes",
    )
    migration = migration_module.Migration

    clamp_index = next(
        index
        for index, operation in enumerate(migration.operations)
        if isinstance(operation, migrations.RunPython)
        and operation.code is migration_module.clamp_mailrule_maximum_age
    )
    alter_index = next(
        index
        for index, operation in enumerate(migration.operations)
        if isinstance(operation, migrations.AlterField)
        and operation.model_name == "mailrule"
        and operation.name == "maximum_age"
    )

    assert migration.atomic is False
    assert clamp_index < alter_index
