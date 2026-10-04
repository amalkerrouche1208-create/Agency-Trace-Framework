# Character-Level Provenance

AgencyTrace reconstructs the document while tracking the causal source of inserted text.

This enables later measures of AI retention and modification without relying on text similarity.

## Provenance origins

Conceptually, surviving text belongs to one of four origin classes:

```text
initial/system
human
AI
other/unknown
```

### Initial/system

Text present in the initial document state.

It is kept separate from authored human and AI text because the initial state may contain prompt material or pre-existing content.

### Human

String content inserted by user-origin text events.

### AI

String content inserted by an API event that has been causally mapped to a reconstructed AI selection.

### Other/unknown

Reserved for text that cannot be assigned to the validated categories.

The validated corpus finishes with zero final other-origin characters.

## Why causal attribution?

AgencyTrace does not ask whether a final phrase *looks similar* to a suggestion.

Instead it follows the event chain:

```text
selection
  → API text insertion
  → inserted character units
  → subsequent retain/delete operations
  → final surviving units
```

This makes AI origin an event-causal property.

## Quill delta replay

Document updates are applied using Quill delta operations in sequence.

The corpus audit found text deltas containing retain, insert, delete, and attribute operations.

String insertions contribute textual characters.

The single observed non-string image embed is treated as a logical position but is excluded from text-character metrics.

## Deletion accounting

When text is deleted, provenance units are deleted with it.

This allows AgencyTrace to compute, for every confirmed AI insertion:

```text
inserted AI characters
surviving AI characters
deleted AI characters
```

At corpus level:

```text
AI inserted      858,779
AI surviving     801,131
AI deleted        57,648
```

The accounting identity holds exactly:

```text
inserted = surviving + deleted
```

## Corpus final provenance

Validated final textual partition:

```text
Final textual characters          3,359,765
Final AI-origin characters          801,131
Final human-origin characters     2,094,218
Final initial/system characters     464,416
Final other-origin characters             0
```

## AI retention

Corpus AI-character retention is:

```text
801,131 / 858,779 = 0.9329
```

Retention measures literal survival of causally attributed AI characters.

It is not a semantic-similarity score and does not indicate correctness or learner agreement.

## Authored-text AI share

The AgencyTrace corpus authored-text AI share excludes initial/system text:

```text
AI-origin final characters
-------------------------------------
AI-origin + human-origin final chars
```

For the validated corpus this is approximately:

```text
0.2767
```

## External final-document validation

The corpus contains an initial `currentDoc` snapshot but no later independent final `currentDoc` snapshot.

Therefore AgencyTrace can validate internal delta/provenance accounting, but it cannot compare every reconstructed final document against an independently recorded final document.

This limitation is explicit in the provenance audit.

## Interpretation boundary

Provenance answers:

> Which observable insertion caused these surviving characters to enter the document?

It does not answer:

> Who intellectually authored the idea?

A user can retype or paraphrase AI content; an AI-origin span can be deeply understood by the learner; human-origin text can itself be copied from elsewhere. Those questions require additional evidence.
