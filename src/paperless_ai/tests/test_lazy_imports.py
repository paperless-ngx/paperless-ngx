import subprocess
import sys


class TestLazyAiImports:
    def test_importing_tasks_does_not_load_ai_libraries(self) -> None:
        code = (
            "import os, django, sys\n"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')\n"
            "django.setup()\n"
            "import documents.tasks  # noqa: F401\n"
            "leaked = [m for m in ('lancedb', 'pyarrow', 'llama_index') "
            "if m in sys.modules]\n"
            "assert not leaked, f'AI libraries leaked into the light path: {leaked}'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd="src",
        )
        assert result.returncode == 0, result.stdout + result.stderr
