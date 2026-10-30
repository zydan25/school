#!/usr/bin/env python
"""Django command-line utility for the School platform."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "تعذر استيراد Django. ثبّت المتطلبات من requirements/dev.txt داخل البيئة الافتراضية."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
