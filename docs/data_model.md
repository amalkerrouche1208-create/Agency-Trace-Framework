# Data Model

AgencyTrace uses a layered data model in which raw observations, reconstructed interaction units, provenance state, and analytical measurements remain distinct.

## Layer 1 — Event

An `Event` represents one observed CoAuthor log record.

Stable analytical fields include:

```text
session identifier
event number
timestamp
event name
event source
text delta (when present)
suggestion/UI state (when present)
```

The event number is the primary within-session ordering signal used by reconstruction.

Events are observations. They are not themselves interpreted as adoption, rejection, agency, or regulation.

## Layer 2 — Suggestion episode

A `SuggestionEpisode` represents one observable suggestion request initiated by `suggestion-get`.

An episode may contain:

- a request event;
- a display/open event;
- reopen evidence;
- zero, one, or multiple selections;
- confirmed API insertion evidence;
- dismissal/close evidence.

The request is the lifecycle anchor.

AgencyTrace does not create an episode merely to explain an otherwise orphan event.

## Layer 3 — Selection

A reconstructed selection is a selection/API-insertion cycle associated with a suggestion episode.

Selections are modeled separately from request episodes because one request can contain more than one observable selection.

The validated corpus contains:

```text
18,103 request episodes
12,812 selections
19 request episodes with more than one selection
maximum selections in one episode: 3
```

## Layer 4 — Provenance state

Document provenance tracks surviving text units by causal insertion source.

The main origins are conceptually:

```text
initial/system
human
AI
other/unknown
```

AI origin is assigned only when an API insertion is causally linked to a reconstructed selection.

This is not a similarity-based attribution system.

## Layer 5 — Selection metrics

Each confirmed selection can be summarized by measures such as:

- inserted AI characters;
- surviving AI characters;
- deleted AI characters;
- retention ratio;
- AgencyTrace adoption class.

These are derived from provenance, not from the raw selection event alone.

## Layer 6 — Session metrics

Session-level outputs aggregate reconstruction/provenance evidence across a session.

AgencyTrace session metrics and historical reproduction indicators are deliberately written to different files.

## Historical request outcome

The historical five-way request-outcome layer uses one output row per `suggestion-get`:

```text
accept_unchanged
accepted_modified
non_adoption
presented_no_selection
request_without_suggestion
```

These labels reproduce a previous analytical convention and must not be conflated with the AgencyTrace three-way selection classification.

## Historical session indicators

The target correlation analysis uses ten session-level variables:

```text
Human Generation Before AI
Consultation Density
AI Contribution
AI Retention
Non-Adoption
Post-AI Editing
Reconsultation
Response Latency
Transition Entropy
Consultation Burstiness
```

Their historical definitions are documented in [Metrics](metrics.md).

## Missingness

Missing evidence is not automatically encoded as zero.

Examples:

- no displayed suggestion is not the same as a displayed suggestion that was not selected;
- no final-document snapshot is not evidence that reconstruction is correct or incorrect;
- an orphan reopen is not force-linked to a fabricated request.

This missingness discipline is essential for later ML work because artificial zeros would create spurious patterns.
