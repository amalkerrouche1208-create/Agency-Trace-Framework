# Data

AgencyTrace separates immutable source traces from reproducible derived data.

```text
data/
├── raw/          # source CoAuthor JSONL sessions
├── processed/    # regenerated session/selection/target metrics
└── analysis/     # regenerated statistical-analysis tables
```

## `raw/`

`data/raw/` contains the CoAuthor interaction corpus used by the current release.

Validated corpus size:

```text
1,447 session files
2,701,458 raw events
```

The raw files are treated as immutable inputs. AgencyTrace does not rewrite them.

The repository tracks `data/raw/**` through Git LFS because the corpus is large.

The loader expects CoAuthor event records containing the fields required by the corresponding event type, including event sequence information, timestamps, event names/sources, Quill deltas for text-changing events, and suggestion information for suggestion UI events.

Session identity is derived from the input file/session trace. AgencyTrace does not infer writer identity, demographic attributes, task categories, or psychological states from filenames or document text.

## `processed/`

`data/processed/` contains deterministic outputs derived from the raw corpus.

Current outputs include:

```text
session_metrics.csv
selection_metrics.csv
target_behavior_metrics.csv
request_outcomes.csv
```

`session_metrics.csv` and `selection_metrics.csv` belong to the modern AgencyTrace layer.

`target_behavior_metrics.csv` and `request_outcomes.csv` belong to the historical reproduction layer and are intentionally kept separate.

These files are generated artifacts and should be rebuilt rather than edited manually.

## `analysis/`

`data/analysis/` contains statistical outputs derived from processed metrics.

Current target outputs include:

```text
target_behavior_correlations.csv
target_behavior_sample_sizes.csv
target_outcomes_by_ai_share.csv
```

These tables are inputs to the validated figure-generation module.

## Regeneration

To rebuild the complete derived-data layer:

```bash
agencytrace reproduce
```

For a faster rerun after corpus audits have already been verified:

```bash
agencytrace reproduce --skip-audits
```

## Integrity policy

AgencyTrace follows four data-handling rules:

1. raw traces are never modified by the analysis pipeline;
2. derived data are regenerated from code rather than manually edited;
3. ambiguous events remain explicit anomalies instead of being force-assigned;
4. modern metrics and historical reproduction metrics are stored separately.

## Dataset attribution

The interaction data originate from the Stanford CoAuthor project by Mina Lee, Percy Liang, and Qian Yang.

AgencyTrace does not change upstream ownership or usage conditions. Anyone redistributing the raw corpus should independently verify that such redistribution is permitted by the applicable CoAuthor terms.
