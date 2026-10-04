# Reproducibility

AgencyTrace is designed so that analytical outputs can be rebuilt from the raw CoAuthor corpus through an explicit sequence of audited stages.

## Environment

Requirements:

```text
Python >= 3.11
NumPy
Matplotlib
```

Development/testing additionally uses Pytest.

Install:

```bash
python -m pip install -e ".[dev]"
```

## Raw corpus

Expected location:

```text
data/raw/
```

Validated corpus:

```text
1,447 sessions
2,701,458 events
```

Raw files are tracked through Git LFS and are never modified by the reproduction pipeline.

## One-command reproduction

Run:

```bash
agencytrace reproduce
```

Equivalent direct script:

```bash
python scripts/reproduce_all.py
```

The full order is:

```text
1. text-delta audit
2. lifecycle audit
3. provenance audit
4. modern metric export
5. modern metric audit
6. historical target reproduction
7. target analysis
8. figure generation
9. release validation
```

Every stage must return a zero exit status before execution continues.

## Fast reproduction

When the expensive corpus audits have already passed:

```bash
agencytrace reproduce --skip-audits
```

This still regenerates:

- modern metrics;
- historical target metrics;
- statistical analysis;
- figures;
- final release validation.

## Generated data

Modern outputs:

```text
data/processed/session_metrics.csv
data/processed/selection_metrics.csv
```

Historical outputs:

```text
data/processed/target_behavior_metrics.csv
data/processed/request_outcomes.csv
```

Analysis outputs:

```text
data/analysis/target_behavior_correlations.csv
data/analysis/target_behavior_sample_sizes.csv
data/analysis/target_outcomes_by_ai_share.csv
```

Publication-oriented outputs:

```text
figures/ai_share_response_outcomes.png
figures/ai_share_response_outcomes.pdf
figures/trace_indicator_correlations.png
figures/trace_indicator_correlations.pdf
```

## Historical compatibility

The historical exporter intentionally preserves definitions needed to reproduce the target analysis.

This includes the one-request-window model and NumPy numerical behavior.

Warnings such as:

```text
RuntimeWarning: Mean of empty slice
RuntimeWarning: invalid value encountered in scalar divide
```

can therefore occur when the historical definition takes the mean of an empty collection.

The resulting `NaN` values are expected compatibility behavior, not automatically a pipeline failure.

## Frozen validation targets

The release validator checks at least the following:

```text
raw sessions                    1,447
modern session rows             1,447
modern selection rows          12,812
historical request rows        18,103
historical five-way counts      exact
correlation matrix              10 x 10
AI-share outcome composition    exact
required PNG/PDF figures        present and non-empty
```

## Tests vs audits

`pytest` and corpus audits serve different purposes.

### Tests

```bash
pytest -q
```

Tests check reusable software behavior using fixtures and targeted integration cases.

### Corpus audits

```bash
agencytrace audit
```

Audits check scientific invariants over the complete corpus.

Both are required before a release.

## Reproduction claim

AgencyTrace currently supports two distinct claims:

1. the modern reconstruction/provenance pipeline satisfies its documented corpus invariants;
2. the historical compatibility layer reproduces the recovered target numerical results.

The repository does **not** claim that every visual styling detail of the historical stacked-bar figure is source-identical.

## Recommended release procedure

```bash
pytest -q
agencytrace audit
agencytrace reproduce
agencytrace validate
git diff --check
git status
```

A release should not be tagged while any scientific audit or release-validation check fails.
