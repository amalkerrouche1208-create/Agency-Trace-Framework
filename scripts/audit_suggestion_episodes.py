from __future__ import annotations

from collections import Counter
from pathlib import Path

from agencytrace.io import load_jsonl_events
from agencytrace.reconstruct import reconstruct_suggestion_episodes


RAW_DIR = Path("data/raw")


def main() -> None:
    paths = sorted(RAW_DIR.rglob("*.jsonl"))

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/"
        )

    # ------------------------------------------------------------------
    # Corpus-level raw counts
    # ------------------------------------------------------------------

    raw_totals: Counter[str] = Counter()

    # ------------------------------------------------------------------
    # Reconstructed counts
    # ------------------------------------------------------------------

    reconstructed_episodes = 0
    reconstructed_selections = 0
    reconstructed_insertions = 0
    reconstructed_dismissed = 0
    reconstructed_reopens = 0

    # ------------------------------------------------------------------
    # Selection diagnostics
    # ------------------------------------------------------------------

    total_missing_selects = 0
    total_extra_selects = 0
    total_duplicate_selects = 0

    selection_mismatch_sessions: list[
        tuple[
            Path,
            set[int],
            set[int],
            set[int],
            list,
        ]
    ] = []

    # ------------------------------------------------------------------
    # Reopen diagnostics
    #
    # A raw suggestion-reopen without any observable prior opened
    # suggestion episode is preserved as an orphan event rather than
    # assigned speculatively.
    # ------------------------------------------------------------------

    total_orphan_reopens = 0
    total_extra_reopens = 0
    total_duplicate_reopens = 0

    orphan_reopen_records: list[
        tuple[
            Path,
            int,
            list,
        ]
    ] = []

    # ------------------------------------------------------------------
    # Behavioral summary
    # ------------------------------------------------------------------

    multi_selection_episodes = 0
    max_selections_per_episode = 0

    # ------------------------------------------------------------------
    # Process complete corpus
    # ------------------------------------------------------------------

    for index, path in enumerate(paths, start=1):
        events = load_jsonl_events(path)

        counts = Counter(
            event.event_name
            for event in events
        )

        raw_totals.update(counts)

        episodes = reconstruct_suggestion_episodes(
            events
        )

        # --------------------------------------------------------------
        # Reconstruction counts
        # --------------------------------------------------------------

        reconstructed_episodes += len(
            episodes
        )

        reconstructed_selections += sum(
            len(episode.selections)
            for episode in episodes
        )

        reconstructed_insertions += sum(
            selection.was_inserted
            for episode in episodes
            for selection in episode.selections
        )

        reconstructed_dismissed += sum(
            episode.was_dismissed
            for episode in episodes
        )

        reconstructed_reopens += sum(
            len(episode.reopen_event_nums)
            for episode in episodes
        )

        # --------------------------------------------------------------
        # Multi-selection episode statistics
        # --------------------------------------------------------------

        for episode in episodes:
            selection_count = len(
                episode.selections
            )

            if selection_count > 1:
                multi_selection_episodes += 1

            max_selections_per_episode = max(
                max_selections_per_episode,
                selection_count,
            )

        # --------------------------------------------------------------
        # SELECT validation
        # --------------------------------------------------------------

        raw_select_nums = [
            event.event_num
            for event in events
            if event.event_name
            == "suggestion-select"
        ]

        reconstructed_select_nums = [
            selection.event_num
            for episode in episodes
            for selection in episode.selections
        ]

        raw_select_set = set(
            raw_select_nums
        )

        reconstructed_select_set = set(
            reconstructed_select_nums
        )

        missing_selects = (
            raw_select_set
            - reconstructed_select_set
        )

        extra_selects = (
            reconstructed_select_set
            - raw_select_set
        )

        reconstructed_select_counter = Counter(
            reconstructed_select_nums
        )

        duplicate_selects = {
            event_num
            for event_num, count
            in reconstructed_select_counter.items()
            if count > 1
        }

        total_missing_selects += len(
            missing_selects
        )

        total_extra_selects += len(
            extra_selects
        )

        total_duplicate_selects += len(
            duplicate_selects
        )

        if (
            missing_selects
            or extra_selects
            or duplicate_selects
        ):
            selection_mismatch_sessions.append(
                (
                    path,
                    missing_selects,
                    extra_selects,
                    duplicate_selects,
                    events,
                )
            )

        # --------------------------------------------------------------
        # REOPEN validation
        # --------------------------------------------------------------

        raw_reopen_nums = [
            event.event_num
            for event in events
            if event.event_name
            == "suggestion-reopen"
        ]

        reconstructed_reopen_nums = [
            event_num
            for episode in episodes
            for event_num
            in episode.reopen_event_nums
        ]

        raw_reopen_set = set(
            raw_reopen_nums
        )

        reconstructed_reopen_set = set(
            reconstructed_reopen_nums
        )

        missing_reopen_nums = (
            raw_reopen_set
            - reconstructed_reopen_set
        )

        extra_reopen_nums = (
            reconstructed_reopen_set
            - raw_reopen_set
        )

        reconstructed_reopen_counter = Counter(
            reconstructed_reopen_nums
        )

        duplicate_reopen_nums = {
            event_num
            for event_num, count
            in reconstructed_reopen_counter.items()
            if count > 1
        }

        total_extra_reopens += len(
            extra_reopen_nums
        )

        total_duplicate_reopens += len(
            duplicate_reopen_nums
        )

        # --------------------------------------------------------------
        # Determine whether unmatched reopen events are true orphans.
        #
        # Because last_displayed is preserved by the reconstructor,
        # an unmatched reopen should have no observable suggestion-open
        # earlier in the session.
        # --------------------------------------------------------------

        for reopen_num in sorted(
            missing_reopen_nums
        ):
            reopen_position = next(
                (
                    i
                    for i, event
                    in enumerate(events)
                    if event.event_num
                    == reopen_num
                ),
                None,
            )

            if reopen_position is None:
                continue

            earlier_events = events[
                :reopen_position
            ]

            has_observable_antecedent = any(
                event.event_name
                in {
                    "suggestion-open",
                    "suggestion-reopen",
                }
                for event in earlier_events
            )

            if not has_observable_antecedent:
                total_orphan_reopens += 1

                orphan_reopen_records.append(
                    (
                        path,
                        reopen_num,
                        events,
                    )
                )

            else:
                # This would indicate an actual reconstruction defect.
                #
                # Treat it as a hard inconsistency rather than silently
                # labelling it an orphan.
                total_extra_reopens += 1

    # ------------------------------------------------------------------
    # Derived differences
    # ------------------------------------------------------------------

    expected_episodes = (
        raw_totals["suggestion-get"]
    )

    episode_difference = (
        reconstructed_episodes
        - expected_episodes
    )

    selection_difference = (
        reconstructed_selections
        - raw_totals["suggestion-select"]
    )

    accounted_reopens = (
        reconstructed_reopens
        + total_orphan_reopens
    )

    reopen_accounting_difference = (
        accounted_reopens
        - raw_totals["suggestion-reopen"]
    )

    # ------------------------------------------------------------------
    # Core invariants
    # ------------------------------------------------------------------

    episode_invariant_ok = (
        reconstructed_episodes
        == raw_totals["suggestion-get"]
    )

    selection_count_invariant_ok = (
        reconstructed_selections
        == raw_totals["suggestion-select"]
    )

    selection_identity_invariant_ok = (
        total_missing_selects == 0
        and total_extra_selects == 0
        and total_duplicate_selects == 0
    )

    insertion_invariant_ok = (
        reconstructed_insertions
        == reconstructed_selections
    )

    reopen_accounting_ok = (
        accounted_reopens
        == raw_totals["suggestion-reopen"]
        and total_extra_reopens == 0
        and total_duplicate_reopens == 0
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "AgencyTrace — CoAuthor Suggestion Lifecycle Audit"
    )
    print("=" * 78)

    print(
        f"Sessions                        : "
        f"{len(paths)}"
    )

    print()
    print("-" * 78)
    print("RAW EVENTS")
    print("-" * 78)

    print(
        f"Raw suggestion-get              : "
        f"{raw_totals['suggestion-get']}"
    )

    print(
        f"Raw suggestion-open             : "
        f"{raw_totals['suggestion-open']}"
    )

    print(
        f"Raw suggestion-reopen           : "
        f"{raw_totals['suggestion-reopen']}"
    )

    print(
        f"Raw suggestion-select           : "
        f"{raw_totals['suggestion-select']}"
    )

    print(
        f"Raw suggestion-close            : "
        f"{raw_totals['suggestion-close']}"
    )

    print()

    print("-" * 78)
    print("RECONSTRUCTED LIFECYCLES")
    print("-" * 78)

    print(
        f"Reconstructed episodes          : "
        f"{reconstructed_episodes}"
    )

    print(
        f"Reconstructed selections        : "
        f"{reconstructed_selections}"
    )

    print(
        f"Reconstructed insertions        : "
        f"{reconstructed_insertions}"
    )

    print(
        f"Reconstructed dismissed         : "
        f"{reconstructed_dismissed}"
    )

    print(
        f"Attributable reopen events      : "
        f"{reconstructed_reopens}"
    )

    print(
        f"Orphan reopen events            : "
        f"{total_orphan_reopens}"
    )

    print()

    print("-" * 78)
    print("VALIDATION")
    print("-" * 78)

    print(
        f"Expected episodes (= get)       : "
        f"{expected_episodes}"
    )

    print(
        f"Episode count difference        : "
        f"{episode_difference:+d}"
    )

    print(
        f"Selection count difference      : "
        f"{selection_difference:+d}"
    )

    print(
        f"Reopen accounting difference    : "
        f"{reopen_accounting_difference:+d}"
    )

    print()

    print(
        f"Unmatched raw selections        : "
        f"{total_missing_selects}"
    )

    print(
        f"Spurious reconstructed selects  : "
        f"{total_extra_selects}"
    )

    print(
        f"Duplicate reconstructed selects : "
        f"{total_duplicate_selects}"
    )

    print()

    print(
        f"Attributable raw reopens        : "
        f"{reconstructed_reopens}"
    )

    print(
        f"Unattributable/orphan reopens   : "
        f"{total_orphan_reopens}"
    )

    print(
        f"Spurious reconstructed reopens  : "
        f"{total_extra_reopens}"
    )

    print(
        f"Duplicate reconstructed reopens : "
        f"{total_duplicate_reopens}"
    )

    print()

    print(
        f"Selection mismatch sessions     : "
        f"{len(selection_mismatch_sessions)}"
    )

    print()

    print("-" * 78)
    print("INVARIANTS")
    print("-" * 78)

    print(
        "One episode per suggestion-get   : "
        f"{'PASS' if episode_invariant_ok else 'FAIL'}"
    )

    print(
        "Raw/reconstructed select count   : "
        f"{'PASS' if selection_count_invariant_ok else 'FAIL'}"
    )

    print(
        "Exact select-event identity       : "
        f"{'PASS' if selection_identity_invariant_ok else 'FAIL'}"
    )

    print(
        "Selection/API insertion pairing   : "
        f"{'PASS' if insertion_invariant_ok else 'FAIL'}"
    )

    print(
        "Reopen event accounting           : "
        f"{'PASS' if reopen_accounting_ok else 'FAIL'}"
    )

    print()

    print("-" * 78)
    print("MULTI-SELECTION EPISODES")
    print("-" * 78)

    print(
        f"Episodes with >1 selection      : "
        f"{multi_selection_episodes}"
    )

    print(
        f"Maximum selections in an episode: "
        f"{max_selections_per_episode}"
    )

    # ------------------------------------------------------------------
    # Selection mismatch diagnostics
    #
    # These indicate real reconstruction problems and therefore remain
    # hard failures.
    # ------------------------------------------------------------------

    if selection_mismatch_sessions:
        print()
        print("=" * 78)
        print("SELECTION RECONSTRUCTION ERRORS")
        print("=" * 78)

        for (
            path,
            missing_selects,
            extra_selects,
            duplicate_selects,
            events,
        ) in selection_mismatch_sessions[:10]:
            print()
            print(path)

            print(
                "missing selects="
                f"{sorted(missing_selects)}"
            )

            print(
                "extra selects="
                f"{sorted(extra_selects)}"
            )

            print(
                "duplicate selects="
                f"{sorted(duplicate_selects)}"
            )

            problematic = (
                missing_selects
                | extra_selects
                | duplicate_selects
            )

            _print_event_context(
                events=events,
                event_nums=problematic,
            )

    # ------------------------------------------------------------------
    # Orphan reopen diagnostics
    #
    # These are raw-data anomalies, not reconstruction failures.
    # ------------------------------------------------------------------

    if orphan_reopen_records:
        print()
        print("=" * 78)
        print("ORPHAN REOPEN EVENTS")
        print("=" * 78)

        print(
            "These events have no observable earlier suggestion "
            "episode and are intentionally left unattributed."
        )

        for (
            path,
            event_num,
            events,
        ) in orphan_reopen_records:
            print()
            print(
                f"{path} "
                f"(reopen event {event_num})"
            )

            _print_event_context(
                events=events,
                event_nums={event_num},
                radius=5,
            )

    # ------------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------------

    all_core_invariants_ok = (
        episode_invariant_ok
        and selection_count_invariant_ok
        and selection_identity_invariant_ok
        and insertion_invariant_ok
        and reopen_accounting_ok
    )

    if not all_core_invariants_ok:
        raise SystemExit(
            "\nLifecycle reconstruction audit FAILED."
        )

    print()
    print("=" * 78)
    print(
        "Lifecycle reconstruction audit PASSED."
    )
    print("=" * 78)


def _print_event_context(
    *,
    events: list,
    event_nums: set[int],
    radius: int = 8,
) -> None:
    """
    Print compact context around selected event numbers.
    """

    for event_num in sorted(event_nums):
        position = next(
            (
                i
                for i, event
                in enumerate(events)
                if event.event_num
                == event_num
            ),
            None,
        )

        if position is None:
            continue

        start = max(
            0,
            position - radius,
        )

        end = min(
            len(events),
            position + radius + 1,
        )

        print()
        print(
            f"--- around event "
            f"{event_num} ---"
        )

        for event in events[start:end]:
            if event.event_num == event_num:
                marker = ">>>"
            else:
                marker = "   "

            print(
                f"{marker} "
                f"{event.event_num:>6}  "
                f"{event.event_name:<22} "
                f"{event.source.value:<7} "
                f"hover="
                f"{event.current_hover_index!r:<5} "
                f"idx="
                f"{event.current_suggestion_index!r:<5}"
            )


if __name__ == "__main__":
    main()