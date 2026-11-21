# data/

Local working directory for datasets. **Nothing in here except this file is committed**
(see `.gitignore`).

- Do not commit third-party datasets. Their licenses often forbid redistribution, and Git is
  the wrong tool for large binary files.
- Loaders read files you downloaded yourself; nothing is downloaded automatically. For the
  Paderborn data see [`docs/datasets.md`](../docs/datasets.md).
- For every dataset you use, fill in a dataset card from
  [`docs/dataset-card-template.md`](../docs/dataset-card-template.md) and keep it with your
  analysis.
