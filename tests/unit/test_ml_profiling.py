from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.profiling import (
    build_cluster_profiles,
)


def test_build_cluster_profiles(
    tmp_path: Path,
) -> None:
    raw = (
        tmp_path
        / "raw.csv"
    )

    assignments = (
        tmp_path
        / "assignments.csv"
    )

    with raw.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "session_id",
                "a",
                "b",
            ]
        )

        writer.writerows(
            [
                ["s1", 1, 10],
                ["s2", 3, 12],
                ["s3", 8, 20],
                ["s4", 10, 22],
            ]
        )

    with assignments.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "session_id",
                "kmeans_k2",
            ]
        )

        writer.writerows(
            [
                ["s1", 0],
                ["s2", 0],
                ["s3", 1],
                ["s4", 1],
            ]
        )

    profiles = (
        build_cluster_profiles(
            raw_matrix=raw,
            assignments=assignments,
            assignment_column=(
                "kmeans_k2"
            ),
        )
    )

    assert len(profiles) == 4

    first = next(
        row
        for row in profiles
        if (
            row["cluster"] == 0
            and row["feature"]
            == "a"
        )
    )

    assert first["n"] == 2
    assert first["median"] == 2.0