# Model card: `<model name>`

Required for every model whose results are reported in this repository (roadmap v0.4+).

## Overview
- **Task:** (e.g. classify healthy / outer race / inner race)
- **Model type and key hyperparameters:**
- **Input features:** (list; link to feature definitions)
- **Code / commit / package version:**

## Training data
- **Datasets (link dataset cards):**
- **Synthetic, real, or both?** If synthetic is involved, say so in the title of every result.
- **Preprocessing:**

## Evaluation
- **Split strategy:** must be by group (machine/recording). State the group column.
- **Metrics:** per-class precision, recall, F1; confusion matrix; confidence intervals.
- **Comparison with a trivial baseline** (majority class, single-feature threshold):
- **Results under shift:** different speed, noise level, machine.

## Explainability
- Which features drive predictions, and do they match the physics (e.g. BPFI ratio for an
  inner-race fault)?

## Limitations and intended use
- **Not validated for operational or safety decisions.**
- Known failure modes and conditions not covered:
