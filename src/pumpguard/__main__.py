"""Allow ``python -m pumpguard <command>``."""

from .cli import main

raise SystemExit(main())
