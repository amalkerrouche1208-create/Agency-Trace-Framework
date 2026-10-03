# CoAuthor input

Place unmodified session logs in `raw/`. Each file represents one session and contains one event object per line, or a JSON array of event objects. Files are read without being rewritten.

This delivery includes only the supplied `7e9c3c8fbe1f4a02bcb9940a2bf95d9f.jsonl` session. The full corpus stored on the author's computer has not been accessed or tested here.

Reconstruction requires `eventNum`, `eventTimestamp` (integer milliseconds), `eventName`, `eventSource`, an initial string `currentDoc`, and valid `textDelta.ops` on text-changing events. Suggestion displays require `currentSuggestions` entries with `index` and `trimmed`; selections are checked against `currentHoverIndex` and the ensuing inserted text. All original event fields remain available through `Event.record`.

Writer identity is absent from the supplied event file. A caller may pass `writer_id` to `load_session` only after joining authoritative metadata. The filename is used as a session identifier, never as a writer identifier. No writing-task category is inferred from text or filename.

The loader preserves the file's SHA-256 digest and source record locations. For JSONL, `source_line` is the physical line number; for a JSON array, it is the one-based array element position.

Source: <https://coauthor.stanford.edu/>. Retain the original dataset documentation and usage terms alongside any full-corpus distribution.
