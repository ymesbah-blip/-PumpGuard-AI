"""Backward-compatible entry point: ``python -m pumpguard.demo [options]``.

Equivalent to ``pumpguard demo [options]``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from .cli import main as _cli_main


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return _cli_main(["demo", *args])


if __name__ == "__main__":
    raise SystemExit(main())
