## What does this change?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Why?

<!-- The problem or research question this addresses. -->

## Engineering assumptions

<!-- Physical or statistical assumptions behind the change (e.g. "impacts excite a single
resonance", "speed is constant within a segment"). Write "none" if purely technical. -->

## Checklist

- [ ] Tests added or updated (`pytest` passes locally)
- [ ] `ruff check .`, `ruff format --check .` and `mypy` pass
- [ ] Public functions have docstrings and type hints
- [ ] `CHANGELOG.md` updated under **Unreleased**
- [ ] Synthetic outputs are labelled as synthetic; no claim of real-world diagnostic accuracy
- [ ] New datasets come with a dataset card (`docs/dataset-card-template.md`), source and license
