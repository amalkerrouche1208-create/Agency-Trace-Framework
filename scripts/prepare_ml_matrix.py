from __future__ import annotations

import json
from pathlib import Path

from agencytrace.ml.preprocessing import (
    export_primary_matrix,
)


DATASET = Path(
    "data/processed/ml_session_features.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml"
)


def main() -> None:
    export_primary_matrix(
        dataset=DATASET,
        output_dir=OUTPUT_DIR,
    )

    manifest_path = (
        OUTPUT_DIR
        / "primary_cluster_manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    print()
    print("=" * 82)
    print(
        "AgencyTrace — ML Matrix Preparation"
    )
    print("=" * 82)

    print(
        f"Total sessions                : "
        f"{manifest['total_sessions']}"
    )

    print(
        f"Included sessions             : "
        f"{manifest['included_sessions']}"
    )

    print(
        f"Excluded sessions             : "
        f"{manifest['excluded_sessions']}"
    )

    print(
        f"Coverage                      : "
        f"{manifest['coverage']:.2%}"
    )

    print(
        f"Primary features              : "
        f"{manifest['feature_count']}"
    )

    for feature in manifest[
        "features"
    ]:
        print(
            f"  - {feature}"
        )

    print()
    print(
        "Scaling                       : "
        "median/IQR"
    )

    print()
    print(
        "Generated:"
    )
    print(
        "  primary_cluster_raw.csv"
    )
    print(
        "  primary_cluster_scaled.csv"
    )
    print(
        "  primary_cluster_manifest.json"
    )

    print("=" * 82)


if __name__ == "__main__":
    main()