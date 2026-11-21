# notebooks/

Exploratory work. Conventions so notebooks stay useful to others:

- Import from the package (`from pumpguard import ...`); move reusable code into `src/` with
  tests instead of copying it between notebooks.
- Fix every random seed and state the package version (`pumpguard.__version__`) at the top.
- Clear outputs before committing (`jupyter nbconvert --clear-output --inplace *.ipynb`).
- Name files `NN_short_topic.ipynb` (e.g. `01_envelope_analysis_tour.ipynb`).
- Label every figure built from synthetic data as synthetic.
