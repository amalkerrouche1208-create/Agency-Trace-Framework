# Roadmap

AgencyTrace development is intentionally staged.

The reconstruction, provenance, historical reproduction, CLI, and release-validation foundation is established first so later machine-learning results can be traced back to auditable behavioral evidence.

## Stage 1 — Reconstruction foundation

Status: **implemented and validated**

Includes:

- CoAuthor event loading;
- request-centered lifecycle reconstruction;
- selection/API insertion pairing;
- reopen accounting;
- character-level causal provenance;
- modern adoption metrics;
- corpus audits.

## Stage 2 — Historical reproducibility

Status: **implemented and validated**

Includes:

- exact five-way historical request outcomes;
- historical session indicators;
- AI-contribution tertiles;
- 10 × 10 Spearman analysis;
- target figures;
- release validation.

## Stage 3 — Feature engineering

Status: **next**

The ML dataset will be built from the modern reconstruction/provenance layer.

Candidate feature families will include:

```text
consultation behavior
response-use behavior
AI-text retention/modification
temporal interaction structure
human generation activity
editing activity
sequence/transition structure
session duration and intensity
```

Every feature will receive a documented definition, source, denominator, missingness rule, and leakage assessment.

## Stage 4 — Descriptive and robustness analysis

Planned:

- distributions;
- missingness analysis;
- outlier diagnostics;
- redundancy/correlation analysis;
- sensitivity to thresholds/windows;
- stability across tasks or session strata where metadata support exists.

## Stage 5 — Unsupervised behavioral modeling

Planned candidates:

- standardized feature-space clustering;
- k-selection diagnostics;
- bootstrap/stability analysis;
- PCA for inspectable structure;
- UMAP only as a visualization aid, not as sole clustering evidence.

No cluster will be given a psychological label solely from geometry.

## Stage 6 — Sequence modeling

Planned:

- first-order transition matrices;
- state-transition entropy;
- transition motifs;
- temporal segmentation;
- trajectory similarity;
- potentially higher-order or hidden-state models if data support and interpretability justify them.

## Stage 7 — Predictive modeling

Potential targets must be defined before model selection.

Evaluation will require:

- train/test separation at the correct unit;
- leakage checks;
- class-balance reporting;
- cross-validation;
- simple baselines;
- calibration where relevant;
- confidence intervals or repeated resampling;
- interpretable feature analysis.

## Stage 8 — Publication outputs

Planned:

- model-comparison tables;
- feature distributions;
- cluster profiles;
- transition diagrams;
- trajectory plots;
- calibrated prediction plots;
- robustness figures.

All publication figures should be generated from code and validated inputs.

## Stage 9 — AgencyTrace interactive tool

The future tool should expose the validated analysis rather than reimplement it.

Potential functions:

```text
load / inspect a session
view reconstructed suggestion episodes
inspect character provenance
view session metrics
compare behavioral profiles
explore transition trajectories
run validated ML models
export figures and tables
```

The tool layer should remain downstream of the scientific Python package.

## Non-goal

AgencyTrace will not use ML to manufacture latent constructs that the trace does not support.

Predictive convenience is not a substitute for construct validity.
