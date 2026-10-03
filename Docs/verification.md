# Verification

Verified on 3 October 2026 with Python 3.12.14.

- The original release passed 29 tests. Version 0.1.1 passes 34 tests, including new refresh, concurrent-request, unanswered-request, display-identity and CLI-summary regressions.
- An offline wheel was built using setuptools 84.0.0 and wheel 0.48.0, installed without runtime dependencies, and executed outside the source directory.
- The supplied session replayed all 3,170 events and 2,766 text changes with zero reconstruction issues.
- Four requests, three selections with matching insertions, and one user dismissal were recovered.
- The final text contains 2,445 Unicode code points. Its SHA-256 digest is `b0f6ade69aeec0802bc434733c30f33da191069e62468896231237567823245f`.
- Final insertion provenance comprises 245 initial, 1,919 writer, 277 AI and 4 API-formatting UTF-16 units.

The final-text digest was independently checked using a plain-string Delta interpreter on this sample. The sample contains no supplementary Unicode characters; separate tests verify UTF-16 offset handling with emoji and reject split surrogate pairs. No later snapshot exists in the sample, so these checks establish implementation consistency rather than agreement with an independently recorded final draft.

Additional tests cover replacement/deletion provenance, selection mismatch, interrupted insertion confirmation, missing indices, dismissal, unknown API text, duplicate records, event gaps, timestamp regressions, malformed JSON, unsupported embeds and document-snapshot disagreement.

The standard editable-install command could not fetch build dependencies because package-index network access was unavailable. Wheel construction and installation were verified offline instead. Python 3.11 compatibility is declared but was not exercised in this environment.

## Version 0.1.1 corpus compatibility correction

The author's terminal output reported 1,446 of 1,447 files reconstructed with version 0.1.0. This was text-replay completion, not confirmation that all provenance was resolved. The failed filename was absent from the supplied excerpt and remains undiagnosed.

The two subsequently supplied sessions were inspected and rerun with version 0.1.1:

- `ef5ff569f6e0458ebb10f2f277612cfe.jsonl`: 9 requests, 8 selections, 8 confirmed insertions, zero issues. Final provenance: 473 initial, 1,282 writer, 863 AI, 6 API-formatting UTF-16 units; no surviving unknown text. Final text SHA-256: `3f4166bff88edd9a59ec2e3e0683782ac5f14c9d9f684a491d5a317ba0dc7950`.
- `ff0d41e1426c410bbf87423713ac5e89.jsonl`: 13 requests, 8 selections, 8 confirmed insertions. Three ambiguous request-to-display links are preserved for concurrent requests at events 2, 3 and 4. The selection at event 14 is nevertheless linked to display 10 and insertion 16. Final provenance: 245 initial, 1,905 writer, 718 AI UTF-16 units; no surviving unknown text. Final text SHA-256: `647846f7ea8e578ba9217b487dbfdc9936d806533db7cc7eb586966d6a5aae4f`.

Both final texts match independent plain-string replay. The initial supplied session retains its original results. The synthetic regression tests preserve the relevant event order without requiring the two new corpus files in the update archive.

The full corpus must be rerun on the author's computer. This stage makes no claim of reproducing the paper's indicator values, clusters, transitions, correlations or figures.
