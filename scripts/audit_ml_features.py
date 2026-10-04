from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median

from agencytrace.ml.features import (
    BEHAVIORAL_FEATURES,
    PROFILE_FEATURES,
)


DATASET = Path(
    "data/processed/ml_session_features.csv"
)

EXPECTED_SESSIONS = 1_447


BOUNDED_01 = {
    "ai_share",
    "ai_retention_ratio",
    "human_generation_before_ai_ratio",
    "dismissal_rate",
    "multi_selection_rate",
    "direct_adoption_share",
    "modified_adoption_share",
}


def _optional_float(
    value: str | None,
) -> float | None:
    if value is None:
        return None

    text = value.strip()

    if text == "":
        return None

    number = float(text)

    if not math.isfinite(number):
        return None

    return number


def main() -> None:
    if not DATASET.is_file():
        raise SystemExit(
            f"Missing ML dataset: {DATASET}"
        )

    with DATASET.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    print()
    print("=" * 82)
    print(
        "AgencyTrace — ML Feature Audit"
    )
    print("=" * 82)

    print(
        f"Sessions                      : "
        f"{len(rows)}"
    )

    if len(rows) != EXPECTED_SESSIONS:
        raise SystemExit(
            f"Expected {EXPECTED_SESSIONS} sessions, "
            f"found {len(rows)}."
        )

    session_ids = [
        row["session_id"]
        for row in rows
    ]

    duplicate_ids = [
        session_id
        for session_id, count
        in Counter(session_ids).items()
        if count > 1
    ]

    print(
        f"Unique session IDs            : "
        f"{len(set(session_ids))}"
    )

    print(
        f"Duplicate session IDs         : "
        f"{len(duplicate_ids)}"
    )

    if duplicate_ids:
        raise SystemExit(
            "Duplicate session IDs found."
        )

    print()
    print("-" * 82)
    print("COMPLETENESS")
    print("-" * 82)

    behavioral_complete = sum(
        int(row["behavioral_complete"])
        for row in rows
    )

    profile_complete = sum(
        int(row["profile_complete"])
        for row in rows
    )

    print(
        f"Behavioral complete           : "
        f"{behavioral_complete}"
    )

    print(
        f"Behavioral incomplete         : "
        f"{len(rows) - behavioral_complete}"
    )

    print(
        f"Profile complete              : "
        f"{profile_complete}"
    )

    print(
        f"Profile incomplete            : "
        f"{len(rows) - profile_complete}"
    )

    print()
    print("-" * 82)
    print("FEATURE DIAGNOSTICS")
    print("-" * 82)

    all_features = list(
        PROFILE_FEATURES
    )

    failures: list[str] = []

    for name in all_features:
        values = [
            _optional_float(
                row.get(name)
            )
            for row in rows
        ]

        observed = [
            value
            for value in values
            if value is not None
        ]

        missing = (
            len(values)
            - len(observed)
        )

        missing_pct = (
            100.0
            * missing
            / len(values)
        )

        if observed:
            minimum = min(observed)
            maximum = max(observed)
            avg = mean(observed)
            med = median(observed)
        else:
            minimum = math.nan
            maximum = math.nan
            avg = math.nan
            med = math.nan

        print()
        print(name)
        print(
            f"  observed                    : "
            f"{len(observed)}"
        )
        print(
            f"  missing                     : "
            f"{missing} "
            f"({missing_pct:.2f}%)"
        )
        print(
            f"  min                         : "
            f"{minimum:.6f}"
        )
        print(
            f"  median                      : "
            f"{med:.6f}"
        )
        print(
            f"  mean                        : "
            f"{avg:.6f}"
        )
        print(
            f"  max                         : "
            f"{maximum:.6f}"
        )

        if name in BOUNDED_01:
            invalid = [
                value
                for value in observed
                if not (
                    0.0
                    <= value
                    <= 1.0
                )
            ]

            print(
                f"  outside [0, 1]              : "
                f"{len(invalid)}"
            )

            if invalid:
                failures.append(
                    f"{name}: "
                    f"{len(invalid)} values outside [0, 1]"
                )

    print()
    print("-" * 82)
    print("FEATURE SETS")
    print("-" * 82)

    print(
        f"Behavioral features           : "
        f"{len(BEHAVIORAL_FEATURES)}"
    )

    print(
        f"Profile features              : "
        f"{len(PROFILE_FEATURES)}"
    )

    if failures:
        print()
        print("FAILURES")

        for failure in failures:
            print(
                f"  - {failure}"
            )

        raise SystemExit(1)

    print()
    print("=" * 82)
    print(
        "ML feature audit PASSED."
    )
    print("=" * 82)


if __name__ == "__main__":
    main()