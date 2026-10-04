# Command-Line Interface

AgencyTrace provides one public command-line entry point:

```bash
agencytrace
```

The equivalent module invocation is:

```bash
python -m agencytrace
```

## Help and version

```bash
agencytrace --help
agencytrace --version
```

Current release:

```text
agencytrace 0.1.1
```

## Commands

```text
reconstruct
audit
export
analyze
figures
reproduce
validate
```

---

## `reconstruct`

Reconstruct suggestion episodes from one CoAuthor session:

```bash
agencytrace reconstruct data/raw/<session-id>.jsonl
```

Reconstruct the complete corpus and print aggregate statistics:

```bash
agencytrace reconstruct data/raw --summary
```

Use another recursive pattern:

```bash
agencytrace reconstruct data/raw --pattern "*.json"
```

A failed input produces a non-zero exit status.

Validated full-corpus summary:

```text
Input files                    : 1447
Successfully reconstructed     : 1447
Failed                         : 0

Events                         : 2701458
Suggestion requests            : 18103
Suggestion selections          : 12812
Dismissed episodes             : 4088
Reopen events                  : 45
```

---

## `audit`

Run all integrity/scientific audits:

```bash
agencytrace audit
```

Run one audit:

```bash
agencytrace audit text-deltas
agencytrace audit lifecycle
agencytrace audit provenance
agencytrace audit metrics
```

The audit commands are intended for scientific verification rather than ordinary data exploration.

---

## `export`

Regenerate both modern and historical processed metrics:

```bash
agencytrace export
```

Modern metrics only:

```bash
agencytrace export modern
```

Historical target reproduction only:

```bash
agencytrace export target
```

Generated files are written under `data/processed/`.

---

## `analyze`

Generate the validated historical target analysis:

```bash
agencytrace analyze
```

Outputs are written under:

```text
data/analysis/
```

The analysis includes:

- historical AI-contribution tertiles;
- five-way request-outcome composition;
- the 10 × 10 Spearman matrix;
- pairwise sample sizes.

---

## `figures`

Generate the validated target figures:

```bash
agencytrace figures
```

Use another output directory:

```bash
agencytrace figures --out outputs/figures
```

Use another analysis directory:

```bash
agencytrace figures \
    --analysis-dir data/analysis \
    --out outputs/figures
```

Standard outputs:

```text
ai_share_response_outcomes.png
ai_share_response_outcomes.pdf
trace_indicator_correlations.png
trace_indicator_correlations.pdf
```

---

## `reproduce`

Run the complete pipeline:

```bash
agencytrace reproduce
```

Skip the expensive audit stages when they have already been verified:

```bash
agencytrace reproduce --skip-audits
```

The command fails immediately if a stage returns a non-zero status.

---

## `validate`

Check the frozen release invariants:

```bash
agencytrace validate
```

Validation checks:

- raw session count;
- modern session/selection metric row counts;
- exact historical five-way reproduction;
- target correlation matrix shape;
- exact AI-share outcome composition;
- required target figure files.

A successful run ends with:

```text
AgencyTrace release validation PASSED.
```

---

## Recommended research workflow

During development:

```bash
pytest -q
agencytrace validate
```

After changing reconstruction/provenance logic:

```bash
agencytrace audit
agencytrace reproduce
```

After changing only plotting code:

```bash
agencytrace figures
agencytrace validate
```

After changing historical analysis definitions:

```bash
agencytrace export target
agencytrace analyze
agencytrace figures
agencytrace validate
```
