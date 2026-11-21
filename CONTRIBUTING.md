# Contributing to PumpGuard AI

Thanks for helping. This project aims to be a trustworthy, reproducible starting point for
rotating-machinery condition-monitoring research, so **correctness and honesty about limits
matter more than features**.

## Ground rules

1. Open an issue describing the problem or proposed feature before large changes.
2. Keep changes small and reproducible.
3. Include tests for feature-extraction or data-processing changes.
4. Document dataset provenance, license, sampling details, and assumptions.
5. Do not present synthetic outputs as real sensor data or claim validated diagnostic accuracy.

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

```bash
git clone https://github.com/<owner>/pumpguard-ai.git
cd pumpguard-ai
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,ml]"   # ml: scikit-learn, for the learned-model tests
pre-commit install          # runs ruff on every commit
```

Before opening a pull request, run what CI runs:

```bash
ruff check . && ruff format --check .
mypy
pytest --cov
```

## Workflow

1. Fork, then create a branch: `git switch -c feat/envelope-kurtogram`.
2. Commit in small steps. [Conventional Commits](https://www.conventionalcommits.org/) are
   encouraged (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
3. Add an entry under **Unreleased** in [`CHANGELOG.md`](CHANGELOG.md).
4. Open a pull request and fill in the template, including the *engineering assumptions*.

## Code standards

- Python ≥ 3.10, type hints on all public functions (`mypy --strict` must pass).
- NumPy-style or Google-style docstrings that state **units** (Hz, s, rpm, mm).
- Validate inputs and raise `ValueError` with a clear message; never fail silently.
- Every random draw goes through a seeded `numpy.random.Generator`.
- No new runtime dependency without discussion in an issue first.

## Tests that mean something

Prefer tests that check physics or maths over tests that only check "it runs":

- analytic values (RMS of a sine is A/√2; Pearson kurtosis of a sine is 1.5);
- known frequencies (a defect at BPFO must produce an envelope peak at BPFO);
- invariants (same seed → same output; `severity=0` → healthy signal);
- invalid input raises a helpful error.

## Adding a synthetic condition

1. Add a `_my_condition(t, cfg, rng)` function in `src/pumpguard/signals.py` and register it
   in `_FAULTS` and `CONDITIONS`.
2. Draw all its randomness *after* the baseline so `severity=0` still reproduces `healthy`.
3. Describe the model, with references, in [`docs/synthetic-model.md`](docs/synthetic-model.md).
4. Add tests showing which feature reveals it, and update the README table.

## Adding a dataset loader

Open a *Dataset proposal* issue first. Loaders read files the user downloaded from a local
path (never commit or download third-party data). They must validate every record with
`pumpguard.datasets.validate_provenance`, offer SHA-256 checksums, ship a completed
[dataset card](docs/dataset-card-template.md), and expose a `group_id` so evaluations can be
split without leakage. Tests use only small invented fixtures that mimic the file format (see
`tests/paderborn_fixtures.py`).

## Scientific integrity

- Label synthetic data as synthetic in code, files (`"synthetic": true`), figures and text.
- Report metrics only with a leakage-safe split (by machine/recording, not by segment) and
  state the split.
- State limitations next to results, not only in a footnote.
- This project is not for operational or safety decisions; do not add wording that implies
  otherwise.

## Governance

Maintainers review and merge pull requests and make final decisions, aiming for consensus in
the issue tracker. Regular, high-quality contributors are invited to become maintainers.
