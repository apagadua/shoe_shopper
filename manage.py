#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shoeshopper.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
