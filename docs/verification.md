# Verification

This document records the frozen validation state of AgencyTrace `v0.1.1`.

Latest corpus verification: **4 October 2026**.

## Software tests

Current public test suite:

```text
8 passed
```

The suite includes CLI tests in addition to reconstruction/provenance fixtures.

Corpus-level scientific verification is performed separately through the audit commands.

## Full-corpus reconstruction

Command:

```bash
agencytrace reconstruct data/raw --summary
```

Validated result:

```text
Input files                    : 1447
Successfully reconstructed     : 1447
Failed                         : 0

Events                         : 2701458
Suggestion requests            : 18103
Suggestion selections          : 12812
Dismissed episodes             : 4088
Reopen events                  : 45

suggestion-get                 : 18103
suggestion-open                : 17012
suggestion-select              : 12812
suggestion-close               : 16967
```

## Lifecycle audit

Validated:

```text
Sessions                        1,447
Reconstructed episodes         18,103
Reconstructed selections       12,812
Reconstructed insertions       12,812
Dismissed episodes              4,088

Attributable reopen events         42
Orphan reopen events                3

Missing raw selections               0
Spurious reconstructed selects       0
Duplicate reconstructed selects      0
Selection mismatch sessions          0

Episodes with >1 selection          19
Maximum selections in an episode     3
```

Core lifecycle invariants pass.

## Provenance audit

Validated:

```text
Raw API text-insert events       12,812
Mapped selection insert events   12,812
Missing insertion mappings            0
Duplicate insertion mappings          0

Raw API inserted characters      858,779
Provenance AI inserted chars     858,779
Insertion-length mismatches            0

AI characters surviving          801,131
AI characters deleted             57,648
AI accounting failures                 0

Final textual characters       3,359,765
Final AI-origin characters       801,131
Final human-origin characters  2,094,218
Final system-origin characters   464,416
Final other-origin characters          0
```

Corpus AI retention ratio:

```text
0.9329
```

Final provenance partition passes.

## Final-document validation boundary

All 1,447 sessions contain an initial `currentDoc`.

No later independent final `currentDoc` snapshot exists in the corpus.

Therefore:

```text
internal delta/provenance validation     PASS
external final-document comparison       N/A
```

This limitation is retained explicitly.

## AgencyTrace metric audit

Validated selection outcomes:

```text
Direct Adoption        7,833
Modified Adoption      4,754
Non-Adoption             225
Total selections       12,812
```

Validated substructure:

```text
complete but interrupted spans   1,694
partial AI survival              3,060
zero AI survival                   225
```

AgencyTrace corpus authored-text AI share:

```text
0.2767
```

## Historical five-way reproduction

Validated exact counts:

```text
accept_unchanged               12,427
accepted_modified                 364
non_adoption                    3,205
presented_no_selection            878
request_without_suggestion      1,229
total                          18,103
```

All historical five-way differences against the recovered reference counts are zero.

## Historical AI-share analysis

Validated thresholds:

```text
Low / Moderate      0.170401
Moderate / High     0.318069
```

Session groups:

```text
Low        483
Moderate   482
High       482
```

Request totals by group:

```text
Low        2,790
Moderate   5,370
High       9,943
```

Outcome composition:

```text
Low       Direct 51.5% | Modified 2.9% | Non 25.5% | NoSel 5.5% | NoSug 14.6%
Moderate  Direct 65.4% | Modified 3.6% | Non 17.8% | NoSel 6.0% | NoSug  7.2%
High      Direct 75.2% | Modified 0.9% | Non 15.5% | NoSel 4.1% | NoSug  4.4%
```

## Historical correlation reproduction

The 10 × 10 Spearman matrix produced by the compatibility layer was compared numerically with the recovered historical reference matrix.

Validated maximum absolute difference:

```text
0.0
```

The numeric heatmap reproduction is therefore exact relative to that recovered matrix.

## Figure generation

Validated outputs:

```text
figures/ai_share_response_outcomes.png
figures/ai_share_response_outcomes.pdf
figures/trace_indicator_correlations.png
figures/trace_indicator_correlations.pdf
```

Figure generation has been verified through both the module and public CLI.

## Release validation

Command:

```bash
agencytrace validate
```

Current validated result:

```text
PASS  Raw sessions: 1447
PASS  Session metrics: 1447
PASS  Selection metrics: 12812
PASS  Historical five-way outcome replication
PASS  10 x 10 target correlation matrix
PASS  Exact AI-share outcome composition
PASS  Target PNG/PDF figures

AgencyTrace release validation PASSED.
```
