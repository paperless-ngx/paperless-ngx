#!/usr/bin/env python3
import os
import sys

if __name__ == "__main__":
    from paperless.version import __full_version_str__

    print(f"[init] Starting Paperless-ngx v{__full_version_str__}")  # noqa: T201

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
