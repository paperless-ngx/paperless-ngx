from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('documents', '1016_auto_20210317_1351'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('document_id', models.PositiveIntegerField()),
                ('user_id', models.PositiveIntegerField())
            ],
        )
    ] 