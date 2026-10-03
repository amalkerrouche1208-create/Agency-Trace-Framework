from __future__ import annotations

from pathlib import Path

from agencytrace.io import load_jsonl_events
from agencytrace.metrics import (
    DIRECT_ADOPTION,
    MODIFIED_ADOPTION,
    NON_ADOPTION,
    compute_selection_metrics,
    compute_session_metrics,
)
from agencytrace.provenance import reconstruct_provenance
from agencytrace.reconstruct import (
    reconstruct_suggestion_episodes,
)


RAW_DIR = Path("data/raw")


def main() -> None:
    paths = sorted(
        RAW_DIR.rglob("*.jsonl")
    )

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/"
        )

    sessions = 0
    total_selections = 0

    # ------------------------------------------------------------------
    # Adoption
    # ------------------------------------------------------------------

    total_direct = 0
    total_modified = 0
    total_non_adoption = 0

    complete_but_interrupted = 0
    partial_survival = 0
    zero_survival = 0

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    inserted_chars = 0
    surviving_chars = 0
    deleted_chars = 0

    final_ai_chars = 0
    final_human_chars = 0
    final_system_chars = 0

    authored_chars = 0

    # ------------------------------------------------------------------
    # Failure counters
    # ------------------------------------------------------------------

    adoption_partition_failures = 0
    direct_semantic_failures = 0
    modified_semantic_failures = 0
    non_adoption_semantic_failures = 0

    provenance_accounting_failures = 0
    authored_partition_failures = 0

    ai_share_bound_failures = 0
    retention_bound_failures = 0

    # ------------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------------

    zero_request_sessions = 0
    zero_selection_sessions = 0
    zero_ai_survival_sessions = 0

    ai_shares: list[float] = []
    retention_ratios: list[float] = []

    # ------------------------------------------------------------------
    # Process corpus
    # ------------------------------------------------------------------

    for index, path in enumerate(
        paths,
        start=1,
    ):
        events = load_jsonl_events(
            path
        )

        episodes = (
            reconstruct_suggestion_episodes(
                events
            )
        )

        provenance = (
            reconstruct_provenance(
                events,
                episodes,
            )
        )

        selection_rows = (
            compute_selection_metrics(
                episodes,
                provenance,
            )
        )

        session = (
            compute_session_metrics(
                events,
                episodes,
                provenance,
            )
        )

        sessions += 1

        total_selections += len(
            selection_rows
        )

        # --------------------------------------------------------------
        # Selection-level semantic audit
        # --------------------------------------------------------------

        direct = 0
        modified = 0
        non_adoption = 0

        for row in selection_rows:
            if (
                row.adoption_outcome
                == DIRECT_ADOPTION
            ):
                direct += 1

                if not (
                    row.inserted_chars > 0
                    and row.surviving_chars
                    == row.inserted_chars
                    and row.deleted_chars == 0
                    and row.survives_contiguously
                    and row.intervening_units == 0
                ):
                    direct_semantic_failures += 1

            elif (
                row.adoption_outcome
                == MODIFIED_ADOPTION
            ):
                modified += 1

                valid_modified = (
                    row.surviving_chars > 0
                    and (
                        row.surviving_chars
                        < row.inserted_chars
                        or not row.survives_contiguously
                    )
                )

                if not valid_modified:
                    modified_semantic_failures += 1

            elif (
                row.adoption_outcome
                == NON_ADOPTION
            ):
                non_adoption += 1

                if (
                    row.surviving_chars
                    != 0
                ):
                    non_adoption_semantic_failures += 1

            else:
                adoption_partition_failures += 1

            # ----------------------------------------------------------
            # Structural subtypes
            # ----------------------------------------------------------

            if (
                row.inserted_chars > 0
                and row.surviving_chars
                == row.inserted_chars
                and not row.survives_contiguously
            ):
                complete_but_interrupted += 1

            if (
                0
                < row.surviving_chars
                < row.inserted_chars
            ):
                partial_survival += 1

            if (
                row.surviving_chars
                == 0
            ):
                zero_survival += 1

        total_direct += direct
        total_modified += modified
        total_non_adoption += (
            non_adoption
        )

        if (
            direct
            + modified
            + non_adoption
            != len(selection_rows)
        ):
            adoption_partition_failures += 1

        # --------------------------------------------------------------
        # Provenance accounting
        # --------------------------------------------------------------

        inserted_chars += (
            session.ai_inserted_chars
        )

        surviving_chars += (
            session.ai_surviving_chars
        )

        deleted_chars += (
            session.ai_deleted_chars
        )

        if (
            session.ai_inserted_chars
            != (
                session.ai_surviving_chars
                + session.ai_deleted_chars
            )
        ):
            provenance_accounting_failures += 1

        # --------------------------------------------------------------
        # Final authored provenance
        # --------------------------------------------------------------

        final_ai_chars += (
            session.final_ai_chars
        )

        final_human_chars += (
            session.final_human_chars
        )

        final_system_chars += (
            session.final_system_chars
        )

        authored_chars += (
            session.authored_text_chars
        )

        if (
            session.authored_text_chars
            != (
                session.final_ai_chars
                + session.final_human_chars
            )
        ):
            authored_partition_failures += 1

        # --------------------------------------------------------------
        # Bounds
        # --------------------------------------------------------------

        if not (
            0.0
            <= session.ai_share
            <= 1.0
        ):
            ai_share_bound_failures += 1

        if not (
            0.0
            <= session.ai_retention_ratio
            <= 1.0
        ):
            retention_bound_failures += 1

        # --------------------------------------------------------------
        # Coverage
        # --------------------------------------------------------------

        if (
            session.suggestion_requests
            == 0
        ):
            zero_request_sessions += 1

        if (
            session.suggestion_selections
            == 0
        ):
            zero_selection_sessions += 1

        if (
            session.final_ai_chars
            == 0
        ):
            zero_ai_survival_sessions += 1

        ai_shares.append(
            session.ai_share
        )

        retention_ratios.append(
            session.ai_retention_ratio
        )

        if index % 100 == 0:
            print(
                f"Processed "
                f"{index}/{len(paths)} "
                f"sessions..."
            )

    # ------------------------------------------------------------------
    # Derived totals
    # ------------------------------------------------------------------

    adoption_total = (
        total_direct
        + total_modified
        + total_non_adoption
    )

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    selection_partition_ok = (
        adoption_total
        == total_selections
        and adoption_partition_failures
        == 0
    )

    direct_semantics_ok = (
        direct_semantic_failures
        == 0
    )

    modified_semantics_ok = (
        modified_semantic_failures
        == 0
    )

    non_adoption_semantics_ok = (
        non_adoption_semantic_failures
        == 0
    )

    provenance_accounting_ok = (
        inserted_chars
        == (
            surviving_chars
            + deleted_chars
        )
        and provenance_accounting_failures
        == 0
    )

    authored_partition_ok = (
        authored_chars
        == (
            final_ai_chars
            + final_human_chars
        )
        and authored_partition_failures
        == 0
    )

    ai_share_bounds_ok = (
        ai_share_bound_failures
        == 0
    )

    retention_bounds_ok = (
        retention_bound_failures
        == 0
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Metrics Audit"
    )
    print("=" * 78)

    print(
        f"Sessions                         : "
        f"{sessions}"
    )

    print(
        f"AI selections                    : "
        f"{total_selections}"
    )

    print()
    print("-" * 78)
    print("ADOPTION OUTCOMES")
    print("-" * 78)

    print(
        f"Direct adoption                  : "
        f"{total_direct}"
    )

    print(
        f"Modified adoption                : "
        f"{total_modified}"
    )

    print(
        f"Non-adoption                     : "
        f"{total_non_adoption}"
    )

    print(
        f"Outcome total                    : "
        f"{adoption_total}"
    )

    if adoption_total:
        print()

        print(
            f"Direct adoption share            : "
            f"{total_direct / adoption_total:.4f}"
        )

        print(
            f"Modified adoption share          : "
            f"{total_modified / adoption_total:.4f}"
        )

        print(
            f"Non-adoption share               : "
            f"{total_non_adoption / adoption_total:.4f}"
        )

    print()
    print("-" * 78)
    print("MODIFICATION STRUCTURE")
    print("-" * 78)

    print(
        f"Complete but interrupted spans   : "
        f"{complete_but_interrupted}"
    )

    print(
        f"Partial AI survival              : "
        f"{partial_survival}"
    )

    print(
        f"Zero AI survival                 : "
        f"{zero_survival}"
    )

    print()
    print("-" * 78)
    print("AI CHARACTER ACCOUNTING")
    print("-" * 78)

    print(
        f"AI inserted characters           : "
        f"{inserted_chars}"
    )

    print(
        f"AI surviving characters          : "
        f"{surviving_chars}"
    )

    print(
        f"AI deleted characters            : "
        f"{deleted_chars}"
    )

    if inserted_chars:
        print(
            f"Corpus AI retention              : "
            f"{surviving_chars / inserted_chars:.4f}"
        )

    print()
    print("-" * 78)
    print("FINAL AUTHORED TEXT")
    print("-" * 78)

    print(
        f"AI-origin characters             : "
        f"{final_ai_chars}"
    )

    print(
        f"Human-origin characters          : "
        f"{final_human_chars}"
    )

    print(
        f"System-origin characters         : "
        f"{final_system_chars}"
    )

    print(
        f"Authored characters              : "
        f"{authored_chars}"
    )

    if authored_chars:
        print(
            f"Corpus authored-text AI share    : "
            f"{final_ai_chars / authored_chars:.4f}"
        )

    print()
    print("-" * 78)
    print("SESSION COVERAGE")
    print("-" * 78)

    print(
        f"Sessions with zero requests      : "
        f"{zero_request_sessions}"
    )

    print(
        f"Sessions with zero selections    : "
        f"{zero_selection_sessions}"
    )

    print(
        f"Sessions with zero final AI text : "
        f"{zero_ai_survival_sessions}"
    )

    if ai_shares:
        print()

        print(
            f"Minimum session AI share         : "
            f"{min(ai_shares):.4f}"
        )

        print(
            f"Maximum session AI share         : "
            f"{max(ai_shares):.4f}"
        )

    if retention_ratios:
        print(
            f"Minimum AI retention             : "
            f"{min(retention_ratios):.4f}"
        )

        print(
            f"Maximum AI retention             : "
            f"{max(retention_ratios):.4f}"
        )

    print()
    print("-" * 78)
    print("INVARIANTS")
    print("-" * 78)

    print(
        "Selection adoption partition      : "
        f"{'PASS' if selection_partition_ok else 'FAIL'}"
    )

    print(
        "Direct-adoption semantics         : "
        f"{'PASS' if direct_semantics_ok else 'FAIL'}"
    )

    print(
        "Modified-adoption semantics       : "
        f"{'PASS' if modified_semantics_ok else 'FAIL'}"
    )

    print(
        "Non-adoption semantics            : "
        f"{'PASS' if non_adoption_semantics_ok else 'FAIL'}"
    )

    print(
        "AI character accounting           : "
        f"{'PASS' if provenance_accounting_ok else 'FAIL'}"
    )

    print(
        "Authored-text provenance partition: "
        f"{'PASS' if authored_partition_ok else 'FAIL'}"
    )

    print(
        "AI-share bounds                   : "
        f"{'PASS' if ai_share_bounds_ok else 'FAIL'}"
    )

    print(
        "Retention-ratio bounds            : "
        f"{'PASS' if retention_bounds_ok else 'FAIL'}"
    )

    all_ok = (
        selection_partition_ok
        and direct_semantics_ok
        and modified_semantics_ok
        and non_adoption_semantics_ok
        and provenance_accounting_ok
        and authored_partition_ok
        and ai_share_bounds_ok
        and retention_bounds_ok
    )

    if not all_ok:
        raise SystemExit(
            "\nMetrics audit FAILED."
        )

    print()
    print("=" * 78)
    print(
        "Metrics audit PASSED."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()