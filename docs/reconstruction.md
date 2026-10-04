# Suggestion Lifecycle Reconstruction

AgencyTrace reconstructs suggestion interactions from temporally ordered CoAuthor events.

The objective is not to create the most convenient narrative. It is to preserve every observable request and selection while avoiding unsupported attribution.

## Reconstruction unit

One `suggestion-get` creates one `SuggestionEpisode`.

Therefore:

```text
number of reconstructed episodes
=
number of observed suggestion-get events
```

For the validated corpus:

```text
suggestion-get events          18,103
reconstructed episodes         18,103
```

## Lifecycle state

The reconstruction logic maintains the observable state needed to distinguish:

- pending requests;
- the currently displayed suggestion episode;
- selection records awaiting their API insertion;
- previously observable episodes that can receive a reopen.

This is necessary because request, display, selection, close, and insertion events do not always occur as a simple one-to-one sequence.

## Requests and displays

A request can exist even when no subsequent suggestion display is observed.

Such a request remains in the reconstructed data.

AgencyTrace does not delete unanswered requests merely because they cannot contribute to a later selection.

## Selections

Selections are reconstructed at event identity level.

The lifecycle audit compares raw `suggestion-select` event numbers with reconstructed selection event numbers.

Validated corpus:

```text
raw suggestion-select              12,812
reconstructed selections           12,812
missing raw selections                  0
spurious reconstructed selections       0
duplicate reconstructed selections      0
selection-mismatch sessions              0
```

## Multiple selections

A request episode can contain more than one selection.

Validated corpus:

```text
episodes with >1 selection    19
maximum selections/episode     3
```

This is why AgencyTrace does not collapse the entire lifecycle to one selection field conceptually, even when compatibility properties expose a first/representative selection.

## API insertion pairing

A selection becomes a confirmed insertion record only when it is paired with the corresponding API text insertion according to the validated lifecycle rules.

The validated corpus contains:

```text
reconstructed selections     12,812
reconstructed insertions     12,812
```

No insertion is fabricated for an unmatched selection.

## Dismissal

A request episode can be marked as dismissed based on observable close/lifecycle evidence.

Validated dismissed episodes:

```text
4,088
```

Dismissal is a UI/behavioral observation. It is not automatically interpreted as disagreement, rejection, or independent decision-making.

## Reopen events

Reopens are attached to the most recently observable episode when the trace provides such an antecedent.

Validated corpus:

```text
raw suggestion-reopen          45
attributable reopen events     42
orphan reopen events            3
```

For an orphan reopen, AgencyTrace retains the anomaly rather than creating a synthetic request episode.

## Event ordering

Reconstruction follows the event sequence represented by the trace.

Timestamp regressions are auditable anomalies; they are not silently used to reorder the interaction into a more convenient sequence.

## Audit invariants

The lifecycle reconstruction is considered valid only when the following hold:

```text
one reconstructed episode per suggestion-get
raw/reconstructed selection counts agree
selection event identities agree
selection/API insertion pairing is internally consistent
reopen accounting is complete
```

The current corpus passes these invariants.

## What reconstruction does not establish

Lifecycle reconstruction alone does not establish:

- trust;
- learning;
- verification;
- cognitive effort;
- agency;
- regulation;
- decision quality.

It establishes the observable interaction structure required before such constructs can be operationalized.
