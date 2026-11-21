# PumpGuard AI

**An open-source starter project for rotating machinery condition monitoring, predictive maintenance, and digital-twin experimentation.**

PumpGuard AI is a learning and research prototype focused on centrifugal-pump health monitoring. It combines a transparent synthetic vibration-data generator, basic signal features, and a simple baseline health indicator. The goal is to build a reproducible engineering workflow before experimenting with real datasets, machine learning models, and digital-twin approaches.

> **Status:** Early research prototype. This project does not diagnose real equipment and is not intended for operational or safety decisions.

## What is included

- Synthetic vibration signal generation for illustrative healthy / imbalance / bearing-like patterns
- Basic time-domain signal features (RMS, peak, crest factor, kurtosis)
- A simple, explainable baseline health score (demonstration only)
- CSV export and a plot of the generated signal
- Clear roadmap toward real datasets, model evaluation, and a digital twin

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pumpguard.demo --condition healthy
```

Run from the repository root. For other examples:

```bash
python -m pumpguard.demo --condition imbalance
python -m pumpguard.demo --condition bearing_like
```

The demo writes a CSV file under `outputs/` and saves a signal plot.

## Project structure

```text
pumpguard-ai/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
├── src/pumpguard/
│   ├── __init__.py
│   ├── signals.py
│   ├── features.py
│   └── demo.py
├── data/                 # Place datasets here; large data is not committed
├── notebooks/             # Exploratory work
├── tests/
└── outputs/               # Generated results (ignored by Git)
```

## Data and reproducibility

The included signal generator is **synthetic** and is not a substitute for measured machine data. Use a fixed random seed for reproducible examples. When real datasets are added, document the source, license, machine configuration, sampling rate, sensor location, and labeling method.


## Planned research roadmap

1. **Signal processing:** FFT spectra, envelope analysis, filtering, and frequency-domain features.
2. **Open datasets:** Add a documented loader for a suitable public bearing/pump dataset; respect dataset terms and licenses.
3. **Machine learning:** Establish baseline classifiers, train/validation/test separation, and metrics (precision, recall, F1, confusion matrix).
4. **Explainability:** Compare model outputs with physically interpretable features and failure-mode assumptions.
5. **Digital twin prototype:** Represent operating state, sensor inputs, model predictions, and uncertainty in a modular simulation.
6. **Engineering validation:** Compare results with measured data and clearly state limitations before making any reliability claims.

## Research questions

- Which vibration features are useful for distinguishing operating conditions in a centrifugal-pump test dataset?
- How does the baseline perform when noise and operating speed vary?
- Can a lightweight digital-twin prototype combine measured signals with a simplified physical model?
- What is the impact of data leakage and class imbalance on reported diagnostic performance?

## Contributions

Issues and pull requests are welcome. Please include reproducible examples, explain the engineering assumptions, and avoid claims of real-world accuracy without validation.


## License
MIT — see `LICENSE`.
