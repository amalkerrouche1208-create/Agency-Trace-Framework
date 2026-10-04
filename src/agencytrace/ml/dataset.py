from __future__ import annotations

import csv
import json
from pathlib import Path

from agencytrace.ml.features import (
    BEHAVIORAL_FEATURES,
    FEATURE_SPECS,
    PROFILE_FEATURES,
    build_session_features,
)


def export_session_ml_dataset(
    *,
    source: Path,
    output: Path,
    manifest: Path,
) -> None:
    if not source.is_file():
        raise FileNotFoundError(
            source
        )

    rows: list[
        dict[str, object]
    ] = []

    with source.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        for row in reader:
            rows.append(
                build_session_features(
                    row
                )
            )

    if not rows:
        raise RuntimeError(
            "No session metrics found."
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "session_id",
        *PROFILE_FEATURES,
        "behavioral_complete",
        "profile_complete",
    ]

    with output.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    name: (
                        ""
                        if row.get(name)
                        is None
                        else row.get(name)
                    )
                    for name
                    in fieldnames
                }
            )

    complete_behavioral = sum(
        int(
            row[
                "behavioral_complete"
            ]
        )
        for row in rows
    )

    complete_profile = sum(
        int(
            row[
                "profile_complete"
            ]
        )
        for row in rows
    )

    manifest.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_data = {
        "source": str(source),
        "output": str(output),
        "rows": len(rows),
        "behavioral_complete_rows": (
            complete_behavioral
        ),
        "profile_complete_rows": (
            complete_profile
        ),
        "behavioral_features": list(
            BEHAVIORAL_FEATURES
        ),
        "profile_features": list(
            PROFILE_FEATURES
        ),
        "features": [
            {
                "name": spec.name,
                "source": spec.source,
                "family": spec.family,
                "description": (
                    spec.description
                ),
                "transform": (
                    spec.transform
                ),
                "leakage_role": (
                    spec.leakage_role
                ),
            }
            for spec in FEATURE_SPECS
        ],
    }

    manifest.write_text(
        json.dumps(
            manifest_data,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )