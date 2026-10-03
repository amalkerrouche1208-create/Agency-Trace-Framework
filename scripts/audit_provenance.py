from __future__ import annotations

from collections import Counter
from pathlib import Path

from agencytrace.io import load_jsonl_events
from agencytrace.provenance import reconstruct_provenance
from agencytrace.reconstruct import reconstruct_suggestion_episodes


RAW_DIR = Path("data/raw")

MAX_DIAGNOSTIC_EXAMPLES = 10


def text_insert_length(delta: object) -> int:
    """
    Return the number of textual characters inserted by a Quill Delta.

    Non-text embeds intentionally contribute zero text characters.
    """

    if not isinstance(delta, dict):
        return 0

    ops = delta.get("ops")

    if not isinstance(ops, list):
        return 0

    total = 0

    for op in ops:
        if not isinstance(op, dict):
            continue

        value = op.get("insert")

        if isinstance(value, str):
            total += len(value)

    return total


def main() -> None:
    paths = sorted(
        RAW_DIR.rglob("*.jsonl")
    )

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/"
        )

    # ------------------------------------------------------------------
    # Corpus totals
    # ------------------------------------------------------------------

    total_events = 0

    total_episodes = 0
    total_selections = 0

    # ------------------------------------------------------------------
    # AI insertion mapping
    # ------------------------------------------------------------------

    raw_api_insert_events = 0
    mapped_ai_insert_events = 0

    missing_insert_event_mappings = 0
    duplicate_insert_event_mappings = 0

    raw_api_text_chars = 0
    provenance_ai_inserted_chars = 0

    insertion_length_failures = 0

    # ------------------------------------------------------------------
    # AI provenance accounting
    # ------------------------------------------------------------------

    provenance_ai_surviving_chars = 0
    provenance_ai_deleted_chars = 0

    selection_accounting_failures = 0

    # ------------------------------------------------------------------
    # Final document provenance composition
    # ------------------------------------------------------------------

    final_text_chars = 0
    final_ai_chars = 0
    final_human_chars = 0
    final_system_chars = 0
    final_other_chars = 0

    # ------------------------------------------------------------------
    # Initial document snapshots
    #
    # CoAuthor currentDoc is observed in this corpus at initialization.
    # It is therefore an initial state, not a final-state ground truth.
    # ------------------------------------------------------------------

    sessions_with_initial_doc = 0
    initial_doc_chars = 0

    sessions_with_later_doc_snapshot = 0

    # ------------------------------------------------------------------
    # Provenance engine diagnostics
    # ------------------------------------------------------------------

    sessions_with_anomalies = 0
    total_anomalies = 0

    anomaly_types: Counter[str] = Counter()

    anomaly_examples: list[
        tuple[
            Path,
            str,
        ]
    ] = []

    insertion_failure_examples: list[
        tuple[
            Path,
            int,
            str,
            int,
            int,
        ]
    ] = []

    accounting_failure_examples: list[
        tuple[
            Path,
            str,
            int,
            int,
            int,
        ]
    ] = []

    # ------------------------------------------------------------------
    # Process full corpus
    # ------------------------------------------------------------------

    for session_index, path in enumerate(
        paths,
        start=1,
    ):
        events = load_jsonl_events(
            path
        )

        total_events += len(
            events
        )

        episodes = (
            reconstruct_suggestion_episodes(
                events
            )
        )

        provenance = reconstruct_provenance(
            events,
            episodes,
        )

        total_episodes += len(
            episodes
        )

        selections = [
            selection
            for episode in episodes
            for selection in episode.selections
        ]

        total_selections += len(
            selections
        )

        # --------------------------------------------------------------
        # Initial currentDoc inspection
        # --------------------------------------------------------------

        initial_event = next(
            (
                event
                for event in events
                if event.event_name
                == "system-initialize"
            ),
            None,
        )

        if (
            initial_event is not None
            and initial_event.current_doc
            is not None
        ):
            sessions_with_initial_doc += 1

            initial_doc_chars += len(
                initial_event.current_doc
            )

        later_doc_snapshots = [
            event
            for event in events
            if (
                event.current_doc
                is not None
                and (
                    initial_event is None
                    or event.event_num
                    != initial_event.event_num
                )
            )
        ]

        if later_doc_snapshots:
            sessions_with_later_doc_snapshot += 1

        # --------------------------------------------------------------
        # Index selection insertion mappings
        # --------------------------------------------------------------

        selection_insert_nums = [
            selection.insert_event_num
            for selection in selections
            if selection.insert_event_num
            is not None
        ]

        mapped_ai_insert_events += len(
            selection_insert_nums
        )

        insertion_counter = Counter(
            selection_insert_nums
        )

        duplicate_insert_event_mappings += sum(
            1
            for count
            in insertion_counter.values()
            if count > 1
        )

        # --------------------------------------------------------------
        # Raw API text insertions
        # --------------------------------------------------------------

        raw_api_events = [
            event
            for event in events
            if (
                event.event_name
                == "text-insert"
                and event.source.value
                == "api"
            )
        ]

        raw_api_insert_events += len(
            raw_api_events
        )

        api_by_event_num = {
            event.event_num: event
            for event in raw_api_events
        }

        # --------------------------------------------------------------
        # Validate API insertion identity and character length
        # --------------------------------------------------------------

        for selection in selections:
            insert_event_num = (
                selection.insert_event_num
            )

            if insert_event_num is None:
                missing_insert_event_mappings += 1
                continue

            event = api_by_event_num.get(
                insert_event_num
            )

            if event is None:
                missing_insert_event_mappings += 1
                continue

            expected_chars = (
                text_insert_length(
                    event.text_delta
                )
            )

            stats = provenance.selections[
                selection.selection_id
            ]

            actual_chars = (
                stats.inserted_chars
            )

            raw_api_text_chars += (
                expected_chars
            )

            if (
                expected_chars
                != actual_chars
            ):
                insertion_length_failures += 1

                if (
                    len(
                        insertion_failure_examples
                    )
                    < MAX_DIAGNOSTIC_EXAMPLES
                ):
                    insertion_failure_examples.append(
                        (
                            path,
                            insert_event_num,
                            selection.selection_id,
                            expected_chars,
                            actual_chars,
                        )
                    )

        # --------------------------------------------------------------
        # AI-character accounting
        # --------------------------------------------------------------

        for selection_id, stats in (
            provenance.selections.items()
        ):
            inserted = (
                stats.inserted_chars
            )

            surviving = (
                stats.surviving_chars
            )

            deleted = (
                stats.deleted_chars
            )

            provenance_ai_inserted_chars += (
                inserted
            )

            provenance_ai_surviving_chars += (
                surviving
            )

            provenance_ai_deleted_chars += (
                deleted
            )

            if (
                inserted
                != surviving + deleted
            ):
                selection_accounting_failures += 1

                if (
                    len(
                        accounting_failure_examples
                    )
                    < MAX_DIAGNOSTIC_EXAMPLES
                ):
                    accounting_failure_examples.append(
                        (
                            path,
                            selection_id,
                            inserted,
                            surviving,
                            deleted,
                        )
                    )

        # --------------------------------------------------------------
        # Final provenance composition
        # --------------------------------------------------------------

        final_text_chars += (
            provenance.final_text_chars
        )

        final_ai_chars += (
            provenance.final_ai_chars
        )

        final_human_chars += (
            provenance.final_human_chars
        )

        for unit in provenance.final_units:
            if unit.is_embed:
                continue

            if unit.selection_id is not None:
                continue

            if unit.origin == "human":
                continue

            if unit.origin == "system":
                final_system_chars += 1
            else:
                final_other_chars += 1

        # --------------------------------------------------------------
        # Provenance engine anomalies
        # --------------------------------------------------------------

        if provenance.anomalies:
            sessions_with_anomalies += 1

            total_anomalies += len(
                provenance.anomalies
            )

            for anomaly in provenance.anomalies:
                if (
                    "retain exceeds document"
                    in anomaly
                ):
                    category = (
                        "retain-exceeds-document"
                    )

                elif (
                    "delete exceeds document"
                    in anomaly
                ):
                    category = (
                        "delete-exceeds-document"
                    )

                elif "non-integer" in anomaly:
                    category = (
                        "invalid-numeric-op"
                    )

                elif "negative" in anomaly:
                    category = (
                        "negative-op"
                    )

                else:
                    category = "other"

                anomaly_types[
                    category
                ] += 1

                if (
                    len(anomaly_examples)
                    < MAX_DIAGNOSTIC_EXAMPLES
                ):
                    anomaly_examples.append(
                        (
                            path,
                            anomaly,
                        )
                    )

        if session_index % 100 == 0:
            print(
                f"Processed "
                f"{session_index}/"
                f"{len(paths)} sessions..."
            )

    # ------------------------------------------------------------------
    # Derived invariants
    # ------------------------------------------------------------------

    insertion_mapping_ok = (
        mapped_ai_insert_events
        == raw_api_insert_events
        and missing_insert_event_mappings
        == 0
        and duplicate_insert_event_mappings
        == 0
    )

    insertion_character_identity_ok = (
        raw_api_text_chars
        == provenance_ai_inserted_chars
        and insertion_length_failures
        == 0
    )

    ai_accounting_ok = (
        selection_accounting_failures
        == 0
        and provenance_ai_inserted_chars
        == (
            provenance_ai_surviving_chars
            + provenance_ai_deleted_chars
        )
    )

    provenance_partition_ok = (
        final_text_chars
        == (
            final_ai_chars
            + final_human_chars
            + final_system_chars
            + final_other_chars
        )
    )

    delta_application_ok = (
        total_anomalies == 0
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "AgencyTrace — CoAuthor Provenance Audit"
    )
    print("=" * 78)

    print(
        f"Sessions                         : "
        f"{len(paths)}"
    )

    print(
        f"Events                           : "
        f"{total_events}"
    )

    print(
        f"Suggestion episodes              : "
        f"{total_episodes}"
    )

    print(
        f"AI selections                    : "
        f"{total_selections}"
    )

    # ------------------------------------------------------------------
    # Initial document state
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("DOCUMENT SNAPSHOTS")
    print("-" * 78)

    print(
        f"Sessions with initial currentDoc : "
        f"{sessions_with_initial_doc}"
    )

    print(
        f"Initial currentDoc characters    : "
        f"{initial_doc_chars}"
    )

    print(
        f"Sessions with later currentDoc   : "
        f"{sessions_with_later_doc_snapshot}"
    )

    if (
        sessions_with_later_doc_snapshot
        == 0
    ):
        print(
            "Final currentDoc ground truth    : "
            "NOT PRESENT IN CORPUS"
        )

    # ------------------------------------------------------------------
    # AI insertion mapping
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("AI INSERTION MAPPING")
    print("-" * 78)

    print(
        f"Raw API text-insert events       : "
        f"{raw_api_insert_events}"
    )

    print(
        f"Mapped selection insert events   : "
        f"{mapped_ai_insert_events}"
    )

    print(
        f"Missing insertion mappings       : "
        f"{missing_insert_event_mappings}"
    )

    print(
        f"Duplicate insertion mappings     : "
        f"{duplicate_insert_event_mappings}"
    )

    print()

    print(
        f"Raw API textual inserted chars   : "
        f"{raw_api_text_chars}"
    )

    print(
        f"Provenance AI inserted chars     : "
        f"{provenance_ai_inserted_chars}"
    )

    print(
        f"Insertion-length mismatches      : "
        f"{insertion_length_failures}"
    )

    # ------------------------------------------------------------------
    # AI provenance
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("AI CHARACTER PROVENANCE")
    print("-" * 78)

    print(
        f"AI characters inserted           : "
        f"{provenance_ai_inserted_chars}"
    )

    print(
        f"AI characters surviving          : "
        f"{provenance_ai_surviving_chars}"
    )

    print(
        f"AI characters deleted            : "
        f"{provenance_ai_deleted_chars}"
    )

    print(
        f"Selection accounting failures    : "
        f"{selection_accounting_failures}"
    )

    if provenance_ai_inserted_chars:
        retention_ratio = (
            provenance_ai_surviving_chars
            / provenance_ai_inserted_chars
        )

        print(
            f"Corpus AI retention ratio        : "
            f"{retention_ratio:.4f}"
        )

    # ------------------------------------------------------------------
    # Final provenance composition
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("FINAL DOCUMENT PROVENANCE")
    print("-" * 78)

    print(
        f"Final textual characters         : "
        f"{final_text_chars}"
    )

    print(
        f"Final AI-origin characters       : "
        f"{final_ai_chars}"
    )

    print(
        f"Final human-origin characters    : "
        f"{final_human_chars}"
    )

    print(
        f"Final system-origin characters   : "
        f"{final_system_chars}"
    )

    print(
        f"Final other-origin characters    : "
        f"{final_other_chars}"
    )

    if final_text_chars:
        corpus_ai_share = (
            final_ai_chars
            / final_text_chars
        )

        print(
            f"Corpus AI character share        : "
            f"{corpus_ai_share:.4f}"
        )

    # ------------------------------------------------------------------
    # Engine diagnostics
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("PROVENANCE ENGINE DIAGNOSTICS")
    print("-" * 78)

    print(
        f"Sessions with anomalies          : "
        f"{sessions_with_anomalies}"
    )

    print(
        f"Total anomalies                  : "
        f"{total_anomalies}"
    )

    for name, count in (
        anomaly_types.most_common()
    ):
        print(
            f"  {name:<30} "
            f"{count}"
        )

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    print()
    print("-" * 78)
    print("INVARIANTS")
    print("-" * 78)

    print(
        "Selection/API insertion mapping   : "
        f"{'PASS' if insertion_mapping_ok else 'FAIL'}"
    )

    print(
        "API insertion character identity  : "
        f"{'PASS' if insertion_character_identity_ok else 'FAIL'}"
    )

    print(
        "AI character accounting           : "
        f"{'PASS' if ai_accounting_ok else 'FAIL'}"
    )

    print(
        "Final provenance partition        : "
        f"{'PASS' if provenance_partition_ok else 'FAIL'}"
    )

    print(
        "Delta application bounds          : "
        f"{'PASS' if delta_application_ok else 'FAIL'}"
    )

    print(
        "External final-doc validation     : "
        "N/A (no final currentDoc snapshot)"
    )

    # ------------------------------------------------------------------
    # Failure diagnostics
    # ------------------------------------------------------------------

    if insertion_failure_examples:
        print()
        print("=" * 78)
        print(
            "AI INSERTION LENGTH MISMATCHES"
        )
        print("=" * 78)

        for (
            path,
            event_num,
            selection_id,
            expected,
            actual,
        ) in insertion_failure_examples:

            print()
            print(path)

            print(
                f"  event        : "
                f"{event_num}"
            )

            print(
                f"  selection    : "
                f"{selection_id}"
            )

            print(
                f"  expected     : "
                f"{expected}"
            )

            print(
                f"  actual       : "
                f"{actual}"
            )

    if accounting_failure_examples:
        print()
        print("=" * 78)
        print(
            "AI CHARACTER ACCOUNTING FAILURES"
        )
        print("=" * 78)

        for (
            path,
            selection_id,
            inserted,
            surviving,
            deleted,
        ) in accounting_failure_examples:

            print()
            print(path)

            print(
                f"  selection : "
                f"{selection_id}"
            )

            print(
                f"  inserted  : "
                f"{inserted}"
            )

            print(
                f"  surviving : "
                f"{surviving}"
            )

            print(
                f"  deleted   : "
                f"{deleted}"
            )

    if anomaly_examples:
        print()
        print("=" * 78)
        print(
            "FIRST PROVENANCE ENGINE ANOMALIES"
        )
        print("=" * 78)

        for (
            path,
            anomaly,
        ) in anomaly_examples:

            print()
            print(path)
            print(
                f"  {anomaly}"
            )

    # ------------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------------

    all_core_invariants_ok = (
        insertion_mapping_ok
        and insertion_character_identity_ok
        and ai_accounting_ok
        and provenance_partition_ok
        and delta_application_ok
    )

    if not all_core_invariants_ok:
        raise SystemExit(
            "\nProvenance audit FAILED."
        )

    print()
    print("=" * 78)
    print(
        "Provenance audit PASSED."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()