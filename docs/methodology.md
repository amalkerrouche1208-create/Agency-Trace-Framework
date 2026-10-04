# Methodology

AgencyTrace is a trace-analytics framework for turning low-level human–AI interaction logs into inspectable behavioral evidence.

Its methodology is built around **observability**, **causal attribution**, and **explicit analytical boundaries**.

## 1. Observation before interpretation

Raw UI events describe actions, not psychological states.

For example:

```text
suggestion-select
```

supports the claim that a suggestion was selected.

It does not, by itself, prove that the learner trusted the AI, delegated judgment, verified the content, or relinquished agency.

AgencyTrace therefore follows the sequence:

```text
event
  → reconstructed interaction
  → provenance / measurable behavior
  → indicator
  → interpretation
```

Interpretive constructs should only be introduced when the required evidence has been operationally defined.

## 2. Request-centered lifecycle reconstruction

The modern reconstruction unit is one `suggestion-get`.

Every observed request produces one request episode.

Later UI events are attributed to observable episodes using lifecycle state rather than by inventing missing requests.

The corpus reconstruction preserves all 18,103 requests.

## 3. Orphan reopen events

A `suggestion-reopen` is associated with the most recently observable suggestion episode when such an antecedent exists.

If a reopen occurs without an observable antecedent, AgencyTrace does not create an artificial episode.

The event remains an **orphan reopen** and is reported by the lifecycle audit.

In the validated corpus:

```text
45 reopen events
42 attributable reopens
3 orphan reopens
```

This preserves the raw evidence while avoiding speculative attribution.

## 4. Selection and insertion are distinct

A `suggestion-select` does not automatically imply that AI text entered the document.

AgencyTrace pairs selections with observable API insertion events.

The validated corpus contains 12,812 raw selections and 12,812 reconstructed selection/insertion records, with no missing or spurious selection identities in the lifecycle audit.

## 5. Causal provenance

AI text origin is assigned through event causality:

```text
reconstructed selection
      +
confirmed API insertion
      ↓
AI-origin text
```

Text similarity is not used to infer AI authorship.

Subsequent user edits can delete or interrupt AI-origin spans while the surviving characters retain their causal origin.

## 6. Modern adoption semantics

Modern AgencyTrace classifies a confirmed AI insertion using its final provenance state.

### Direct Adoption

All inserted AI characters survive and remain contiguous without foreign-origin interruption.

### Modified Adoption

Some AI-origin text survives, but the original span is partially deleted or interrupted.

### Non-Adoption

No AI-origin characters from the insertion survive.

These categories describe observable text-use outcomes, not epistemic agreement.

## 7. Authored-text AI share

Modern AI share is measured over final authored text:

```text
final AI-origin characters
----------------------------------------------
final AI-origin + final human-origin characters
```

Initialization/system text is excluded.

This differs from the historical AI-contribution metric used for reference reproduction.

## 8. Historical reproduction as a compatibility layer

The historical target analysis used a simpler request-window model.

AgencyTrace reproduces it separately because changing its definitions would prevent direct comparison with the established target outputs.

Each historical window:

1. begins at `suggestion-get`;
2. ends at the next `suggestion-get`;
3. uses the first `suggestion-open`;
4. uses the first `suggestion-select`;
5. uses the first API `text-insert` after that selection in the same window.

This compatibility model must not be interpreted as the modern AgencyTrace lifecycle model.

## 9. Statistical analysis

The current historical target analysis includes:

- tertile grouping by historical AI contribution;
- five-way request-outcome composition;
- pairwise-complete Spearman correlations among ten historical indicators;
- sample-size reporting for every correlation pair.

No causal claim is made from correlation.

## 10. Scientific boundaries

The current release does not infer unsupported constructs such as:

- critical thinking;
- trust;
- verification;
- monitoring;
- decision authority;
- pedagogical responsibility;
- cognitive offloading;
- dependency.

Those constructs may become model targets only after explicit operationalization and validation.

## 11. ML implications

Future machine-learning analyses will be built on the modern reconstruction/provenance layer.

Before modeling, every feature will be documented with:

```text
unit of analysis
source events
formula
missingness rule
time window
normalization
potential leakage
interpretive boundary
```

This is intended to prevent high-performing but scientifically meaningless models.
