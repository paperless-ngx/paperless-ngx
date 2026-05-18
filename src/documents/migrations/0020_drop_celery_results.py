from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0019_task_system_redesign"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS django_celery_results_taskresult;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS django_celery_results_groupresult;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS django_celery_results_chordcounter;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DELETE FROM django_migrations WHERE app = 'django_celery_results';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
