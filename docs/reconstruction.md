# Reconstruction rules

## Selection evidence

Requests and displays have separate lifecycles. A `suggestion-get` records a request without replacing the currently visible panel. A later `suggestion-close` closes that panel; it cannot consume the new request waiting for a response. Every `suggestion-open` creates a distinct candidate-set identity. A new display supersedes the previous display if it was still visible.

Request-to-display links use an explicit adapter assumption: each successful request supplies one new display. A serial request can therefore be linked to its display. If multiple requests overlap, all possible request links within the batch are retained until the corresponding number of displays has arrived. Response arrival order is never treated as request order. `request_event` and request timing remain unavailable for ambiguous displays, with an `ambiguous_request_link` issue. Lost responses, duplicate displays or interface-specific reopen behavior can violate that assumption and require review; it is not a replacement for request IDs.

An unmatched display still has observable text and an event number. Its selected insertion can be confirmed even if the request link is unavailable. Suggestion identity is `(display event, candidate index)` so two unlinked displays never share provenance accidentally. A request with no observed response remains in `Reconstruction.requests`; it is not automatically a learning episode or a zero-result response.

`suggestion-up`, `suggestion-down`, hover and unhover events are retained as navigation evidence. At selection, a valid integer `currentHoverIndex` identifies the candidate. `currentSuggestionIndex` is not used as a speculative fallback. These are adapter rules checked against the supplied logs, not a claim of coverage of every interface version.

Confirmation requires the next text-changing event after selection to be an API insertion with one inserted string matching the candidate. An intervening API close can finish the display lifecycle without erasing the pending selection. An intervening user edit, another request or a new display invalidates confirmation.

An exact match preserves all candidate characters as AI-origin insertion. If only surrounding whitespace differs, the matching text receives AI provenance and its surrounding inserted whitespace receives `api_formatting`. No fuzzy or semantic matching is performed. An unmatched API insertion remains `unknown` and produces an issue.

A user close without selection is recorded as `dismissed`. It does not establish epistemic rejection, non-adoption of every candidate or a latent reliance state. For interface context, the [CoAuthor interface documentation](https://github.com/minalee-research/coauthor-interface#frontend) describes repeated requests, keyboard navigation and reopening previous suggestions.

## Document provenance

The starting document receives `initial` provenance: its contents may combine prompt material and pre-existing text. User insertions receive `writer` provenance. This records insertion source, not original intellectual authorship. Pasting and undo/redo may reinsert earlier AI text as a user event; this stage does not infer its earlier origin.

Retained text keeps its insertion provenance. Deletions are recorded by origin and, for confirmed AI text, by display event and suggestion index. Surviving AI units describe literal persistence; they do not measure semantic retention, text quality or the paper's AI-contribution indicator without a specified denominator and operational definition.

Each final span stores UTF-16 offsets and its originating event number. Each session stores the input digest and source path. Populated post-initialization `currentDoc` values are checked as post-event snapshots; empty strings are treated as absent snapshots. The supplied sample has no later document snapshot, so replay cannot be validated against an independently recorded final draft.

Quill represents edits with insert, retain and delete operations; unmentioned trailing text is retained. Formatting attributes do not change the plain-text content reconstructed here. See the [Quill Delta specification](https://quilljs.com/docs/delta).

## Scientific boundary

This stage supports the trace reconstruction prerequisite described in manuscript sections 4.2–4.3. It does not implement Algorithm 1 or compute Table 2 indicators. Verification, monitoring, explicit delegation, decision authority and teacher intervention require corresponding evidence; none is inferred from selection or editing alone.

Before subsequent stages, the author must specify learning-episode boundaries, indicator formulas and denominators, clustering configuration, transition states and reliance-shift rules. Suggestion lifecycles may inform those choices but are not automatically learning episodes.
