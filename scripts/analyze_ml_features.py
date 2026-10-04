from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.diagnostics import (
    export_feature_diagnostics,
)


DATASET = Path(
    "data/processed/ml_session_features.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml"
)


def main() -> None:
    export_feature_diagnostics(
        dataset=DATASET,
        output_dir=OUTPUT_DIR,
    )

    diagnostics_path = (
        OUTPUT_DIR
        / "feature_diagnostics.csv"
    )

    strong_path = (
        OUTPUT_DIR
        / "strong_correlations.csv"
    )

    with diagnostics_path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        diagnostics = list(
            csv.DictReader(handle)
        )

    with strong_path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        strong = list(
            csv.DictReader(handle)
        )

    zero_dominated = [
        row["feature"]
        for row in diagnostics
        if row[
            "zero_dominated"
        ] == "1"
    ]

    print()
    print("=" * 82)
    print(
        "AgencyTrace — ML Feature Diagnostics"
    )
    print("=" * 82)

    print(
        f"Dataset                       : "
        f"{DATASET}"
    )

    print(
        f"Features diagnosed            : "
        f"{len(diagnostics)}"
    )

    print(
        f"Zero-dominated features       : "
        f"{len(zero_dominated)}"
    )

    for name in zero_dominated:
        print(
            f"  - {name}"
        )

    print(
        f"Strong correlations |rho|>=.70: "
        f"{len(strong)}"
    )

    for row in strong[:10]:
        print(
            f"  {row['feature_a']} "
            f"<-> {row['feature_b']} "
            f"rho={float(row['spearman_rho']):.3f}"
        )

    print()
    print("Generated:")
    print(
        "  feature_diagnostics.csv"
    )
    print(
        "  feature_spearman.csv"
    )
    print(
        "  feature_pairwise_n.csv"
    )
    print(
        "  missingness_patterns.csv"
    )
    print(
        "  strong_correlations.csv"
    )

    print("=" * 82)


if __name__ == "__main__":
    main()