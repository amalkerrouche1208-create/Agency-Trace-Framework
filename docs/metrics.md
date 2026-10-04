# Metrics

AgencyTrace currently contains two metric families:

1. **modern AgencyTrace metrics**, derived from the validated lifecycle and causal-provenance model;
2. **historical reproduction metrics**, preserved to reproduce the established reference analysis.

They must not be mixed silently.

---

## Modern metrics

### Selection-level retention

For one confirmed AI insertion:

```text
retention ratio
=
surviving AI-origin characters
/
inserted AI-origin characters
```

### Direct Adoption

A selection is **Direct Adoption** when:

- all inserted AI characters survive; and
- the surviving AI-origin span remains contiguous without foreign-origin interruption.

Validated count:

```text
7,833
```

### Modified Adoption

A selection is **Modified Adoption** when AI-origin text survives but:

- some AI characters were deleted; or
- the surviving AI span is interrupted by foreign-origin text.

Validated count:

```text
4,754
```

This includes:

```text
complete but interrupted spans    1,694
partial AI survival               3,060
```

### Non-Adoption

A selection is **Non-Adoption** when no AI-origin character from the confirmed insertion survives.

Validated count:

```text
225
```

### Corpus AI retention

```text
surviving AI characters / inserted AI characters
=
801,131 / 858,779
=
0.9329
```

### Authored-text AI share

Modern session/corpus AI share excludes initialization/system text:

```text
final AI-origin characters
/
(final AI-origin + final human-origin characters)
```

Validated corpus value:

```text
0.2767
```

The corresponding modern session-level tertiles are not the historical target tertiles and should not be used to reproduce the reference stacked-bar figure.

---

# Historical reproduction metrics

The historical layer uses one request window per `suggestion-get`.

Each window ends at the next request and uses:

```text
first suggestion-open
first suggestion-select
first API text-insert after that selection
```

when those events exist.

## Historical five-way request outcomes

The historical response-composition figure uses:

### `accept_unchanged`

A selection and API insertion are observed and the inserted text exactly matches the selected suggestion text.

### `accepted_modified`

A selection and API insertion are observed but the inserted text does not exactly match the selected suggestion text.

### `non_adoption`

A suggestion is displayed and closed by the user without a qualifying selection/insertion outcome.

### `presented_no_selection`

A suggestion is displayed but no qualifying selection is observed and the request does not meet the historical non-adoption close rule.

### `request_without_suggestion`

A request occurs without an observed suggestion display in its historical request window.

Validated totals:

```text
accept_unchanged               12,427
accepted_modified                 364
non_adoption                    3,205
presented_no_selection            878
request_without_suggestion      1,229
total                          18,103
```

---

## Historical session indicators

The historical 10 × 10 Spearman analysis uses the following variables.

### Human Generation Before AI

Median number of user-inserted characters in the 30 seconds immediately preceding each suggestion request.

### Consultation Density

```text
number of suggestion requests
/
session duration in minutes
```

### AI Contribution

Historical AI contribution is:

```text
historical AI inserted characters
/
(user inserted characters + historical AI inserted characters)
```

Historical AI characters use at most one qualifying AI insertion per request window.

This is different from modern final authored-text AI share.

### AI Retention

Mean retained fraction for qualifying historical adopted AI insertions.

### Non-Adoption

Proportion of valid displayed historical response episodes classified as `Non-Adoption`.

### Post-AI Editing

For each displayed episode, count user `text-insert` and `text-delete` events in the post-response window.

The window starts after the insertion timestamp when an insertion exists, otherwise after the suggestion-open timestamp, and ends at the earlier of:

```text
30 seconds later
or
the next suggestion request
```

The session indicator is the median of these counts.

### Reconsultation

For each request except the last:

```text
1 if the next suggestion request occurs within 60 seconds
0 otherwise
```

The session metric is the mean of these flags.

### Response Latency

For each displayed suggestion, latency is measured from `suggestion-open` to the first meaningful user event among:

```text
suggestion-select
suggestion-close
text-insert
text-delete
cursor-forward
cursor-backward
```

The session indicator is the median valid latency in seconds.

### Transition Entropy

Historical response-use states are converted into adjacent transition pairs.

The entropy of the observed transition-pair distribution is normalized by the maximum entropy for the number of observed pair types.

A value near zero indicates highly repetitive observed transitions; larger values indicate a more distributed transition pattern.

### Consultation Burstiness

Computed from inter-request intervals using:

```text
(std - mean) / (std + mean)
```

with population standard deviation (`ddof=0`).

The measure is undefined when too few request intervals exist or when its denominator is not positive.

---

## AI-share groups in the target analysis

Sessions are grouped by historical AI contribution into three equal-frequency groups:

```text
Low        483 sessions
Moderate   482 sessions
High       482 sessions
```

Validated historical contribution thresholds:

```text
Low / Moderate      0.170401
Moderate / High     0.318069
```

Request-outcome totals by group:

```text
Low        2,790
Moderate   5,370
High       9,943
```

These are historical reproduction groups, not modern AgencyTrace AI-share groups.

---

## Missingness

AgencyTrace preserves missing/undefined values where a metric cannot be computed.

Historical reproduction intentionally retains the original NumPy behavior for some empty means, including `NaN` values required for exact numerical compatibility.
