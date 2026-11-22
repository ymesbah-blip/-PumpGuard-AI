# Review of PR #12: Paderborn real3 evidence

Date: 2026-11-22. Reviewed head: `d203b5eed799f6bea33f0ea8c965ac1fc7639e98` on
`feat/paderborn-real3-evidence`, base `main` at `68848a5`. Read-only review; no commit was
added to the PR.

## Verdict

**Ready to merge, subject to the project owner's decision.** No blocking finding. Four
low-severity items are listed below as follow-ups; none requires a change to `d203b5e`.

## Status checks (GitHub REST API, 2026-11-22)

| Item | Result |
|---|---|
| State | open, not merged, `mergeable_state = clean` |
| Position | 1 commit ahead of `main`, 0 behind |
| CI on the head commit | 9 of 9 check runs `success`: lint and type-check; tests on Python 3.10, 3.11, 3.12, 3.13 (Ubuntu), 3.12 (macOS), 3.12 (Windows); tests without the `[ml]` extra; wheel build and smoke test |
| Reviews and comments | none |
| Changed files | 25 |
| Raw data | none: no `.mat`, `.rar`, `.zip`, `.7z`, `.npz` or `.h5` file in the diff |

## Evidence hashes

The four result files match the SHA-256 values recorded in the amendment (section 2.1), the PR
body and the config JSON. Checked against the files served by GitHub and against the local
branch; `scripts/protocol/check_amendment2.py` re-checks them on every test run.

| File | SHA-256 |
|---|---|
| `benchmark_results.json` | `8a5049e42cc412904240c0768a34e090d65128ebcf288274c3d810bb76f4bf01` |
| `leakage_results.json` | `dbd31fce4e6ab4fedf95694a60678805749d10defd7210fe0f6f054ac598a250` |
| `feature_table_provenance.json` | `0bd2d22d270f5a4da06456cd5d18b02f96d276b83ece4345426da10aa90d2f20` |
| `paderborn_verification.json` | `77ad58199cd0789a78cc28c57b6853bb3d784049977aebac63440d2a17e797aa` |

## Version label `pumpguard_version: "0.3.0"`

- The run used commit `1d8d1ab` plus the reader fix and the archive-verification module of the
  evidence commit.
- Between `1d8d1ab` and the v0.4.0 release commit `90e2282`, `src/` and `tests/` differ only in
  `_version.py` (`"0.3.0"` → `"0.4.0"`).
- The label is therefore the version string the code carried at run time, not a different
  analysis. The result files stay unchanged: rewriting the label would break their hashes.
- The results record no commit hash, so the code state is reconstructed. Amendment 2 gate G3
  checks it empirically: the v0.5 code must reproduce R0 = 0.4685836297141851 (within 1e-9) and
  the five outer folds.
- The outer folds were recomputed from the stored bearing labels with
  `stratified_group_kfold(seed=0)` and match the G3 list.

## `scripts/paderborn/fetch_real3.ps1`: security and error handling

What the script does well:

- Downloads only from `https://zenodo.org/records/15845309/files/<name>`, with names taken from
  the committed manifest, so no URL comes from user input.
- Checks size and MD5 against the manifest before extraction, deletes a mismatching file and
  retries at most 3 times.
- Resumes partial downloads (`curl -C -`) and deletes a file larger than expected.
- Checks free disk space first and stops with a clear message.
- Executes nothing it downloads; it only extracts archives with `tar.exe` or 7-Zip.
- Writes only under its own folder and logs every archive to `real3_fetch_log.csv`.

Findings (all low severity, none blocking):

| # | Finding | Risk | Suggested follow-up (separate PR) |
|---|---|---|---|
| F1 | MD5 detects corruption but not deliberate tampering | Low: Zenodo publishes MD5 only, and the manifest pins the values | Record SHA-256 of each verified archive in `paderborn_verification.json` so later checks use a strong hash |
| F2 | Extraction trusts archive paths (`tar -xf`, `7z x -y`) | Low: archives are MD5-pinned; Windows `tar` (bsdtar) refuses `..` entries by default; `-y` lets 7-Zip overwrite files | List entries first and reject absolute or `..` paths; extract each archive into its bearing folder |
| F3 | Usage line recommends `-ExecutionPolicy Bypass` | Low: applies to that one process only, but it skips the policy check | Document `-ExecutionPolicy Bypass` as process-scoped and ask the user to read the script first, or suggest `Unblock-File` followed by a normal run |
| F4 | Script exits 0 when an archive fails | Low: the failure is printed and logged | `exit 1` when `$bad.Count -gt 0`, so automation can stop |

## Licensing and citation

- The original data are CC BY-NC 4.0 (Lessmeier et al., 2016, KAt-DataCenter, Paderborn
  University). The Zenodo mirror is labelled CC BY 4.0. The script header, the results README
  and the dataset page all say that a mirror cannot relax the original licence and that the
  files are treated as CC BY-NC 4.0. Correct.
- The per-segment feature table is not committed; only aggregate results and one figure are.
- Follow-up (low): the repository licence is MIT. Add a short NOTICE, or a "Third-party data"
  section in the README, stating that `docs/results/paderborn-real3/` and
  `docs/images/paderborn_real3.png` derive from CC BY-NC 4.0 data, that attribution is
  required, and that the MIT licence covers the code only.

## Proposed PR comment (not posted)

Posting is a public action and needs the owner's approval.

> Review of `d203b5e` (no new commits):
>
> - CI: 9/9 checks passed on the head commit.
> - Download script: downloads only from the pinned Zenodo record, verifies size and MD5 before
>   extraction, executes nothing it downloads and writes only under its own folder. Low-severity
>   follow-ups for a separate PR: record SHA-256 after verification, reject absolute or `..`
>   archive paths, document the process-scoped execution policy, exit non-zero on failure.
> - Provenance: the `pumpguard_version: "0.3.0"` label is the version string of commit `1d8d1ab`;
>   `src/` and `tests/` differ from v0.4.0 only in `_version.py`. The result files stay unchanged.
>   Amendment 2 gate G3 checks the reconstruction (R0 = 0.4685836297141851, five outer folds).
> - Licence: treated as CC BY-NC 4.0 throughout; a NOTICE for derived results follows separately.
> - v0.5 freeze and execution are out of scope for this PR.
