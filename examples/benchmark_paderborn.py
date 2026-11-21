"""Run the pre-registered Paderborn benchmark end to end.

Prerequisite: you downloaded and extracted the Paderborn KAt bearing data yourself
(CC BY-NC 4.0, non-commercial use with citation). Nothing is downloaded here.

Usage:
    python examples/benchmark_paderborn.py /path/to/paderborn --out outputs/paderborn
    python examples/benchmark_paderborn.py /path/to/paderborn --quick   # 2 measurements/setting

For every task in docs/benchmark-protocol.md this writes a feature table (+ provenance JSON)
and a benchmark report (report.md, results.json). The data come from a bearing test rig, so
the reports must not be read as validation of pump diagnosis.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pumpguard.cli import main as cli

TASKS = ("real3", "artificial_to_real")


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="folder with the extracted .mat files")
    parser.add_argument("--out", type=Path, default=Path("outputs/paderborn"))
    parser.add_argument("--quick", action="store_true", help="use measurements 1-2 only")
    args = parser.parse_args()

    cli(["paderborn", "index", str(args.root)])
    for task in TASKS:
        features = args.out / f"features_{task}.csv"
        extra = ["--max-measurements", "2"] if args.quick else []
        try:
            cli(["paderborn", "features", str(args.root), "--task", task, "--out", str(features),
                 *extra])  # fmt: skip
            cli(["benchmark", str(features), "--out", str(args.out / f"benchmark_{task}")])
        except SystemExit as exc:  # e.g. bearings of this task not downloaded
            print(f"task {task} skipped (exit code {exc.code}); see the message above")
    print(f"Done. Reports are in {args.out}/benchmark_*/report.md")


if __name__ == "__main__":
    run()
