from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Iterable


def _load_csv(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def build_cluster_profiles(
    *,
    raw_matrix: Path,
    assignments: Path,
    assignment_column: str,
) -> list[dict[str, object]]:
    raw_rows = _load_csv(
        raw_matrix
    )

    assignment_rows = _load_csv(
        assignments
    )

    raw_by_session = {
        row["session_id"]: row
        for row in raw_rows
    }

    groups: dict[
        int,
        list[dict[str, str]],
    ] = defaultdict(list)

    for row in assignment_rows:
        session_id = row[
            "session_id"
        ]

        if session_id not in raw_by_session:
            continue

        cluster = int(
            row[
                assignment_column
            ]
        )

        groups[
            cluster
        ].append(
            raw_by_session[
                session_id
            ]
        )

    if not groups:
        raise RuntimeError(
            f"No assignments found for "
            f"{assignment_column}."
        )

    feature_names = [
        name
        for name in raw_rows[0]
        if name != "session_id"
    ]

    output: list[
        dict[str, object]
    ] = []

    total = sum(
        len(rows)
        for rows in groups.values()
    )

    for cluster in sorted(
        groups
    ):
        members = groups[
            cluster
        ]

        for feature in feature_names:
            values = [
                float(
                    row[feature]
                )
                for row in members
            ]

            output.append(
                {
                    "solution": (
                        assignment_column
                    ),
                    "cluster": cluster,
                    "feature": feature,
                    "n": len(members),
                    "cluster_fraction": (
                        len(members)
                        / total
                    ),
                    "mean": mean(values),
                    "median": median(
                        values
                    ),
                    "min": min(values),
                    "max": max(values),
                }
            )

    return output


def export_cluster_profiles(
    *,
    raw_matrix: Path,
    assignments: Path,
    output: Path,
    assignment_columns: Iterable[str],
) -> None:
    rows: list[
        dict[str, object]
    ] = []

    for column in assignment_columns:
        rows.extend(
            build_cluster_profiles(
                raw_matrix=raw_matrix,
                assignments=assignments,
                assignment_column=column,
            )
        )

    if not rows:
        raise RuntimeError(
            "No cluster profiles generated."
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            rows
        )