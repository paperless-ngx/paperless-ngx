from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0009_alter_applicationconfiguration_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicationconfiguration",
            name="llm_backend",
            field=models.CharField(
                blank=True,
                choices=[
                    ("openai", "OpenAI"),
                    ("ollama", "Ollama"),
                    ("minimax", "MiniMax"),
                ],
                max_length=128,
                null=True,
                verbose_name="Sets the LLM backend",
            ),
        ),
    ]
