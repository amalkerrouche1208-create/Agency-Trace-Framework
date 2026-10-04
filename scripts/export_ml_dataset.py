from __future__ import annotations

from pathlib import Path

from agencytrace.ml.dataset import (
    export_session_ml_dataset,
)


SOURCE = Path(
    "data/processed/session_metrics.csv"
)

OUTPUT = Path(
    "data/processed/ml_session_features.csv"
)

MANIFEST = Path(
    "data/processed/ml_session_features_manifest.json"
)


def main() -> None:
    export_session_ml_dataset(
        source=SOURCE,
        output=OUTPUT,
        manifest=MANIFEST,
    )

    print()
    print("=" * 78)
    print(
        "AgencyTrace — ML Feature Export"
    )
    print("=" * 78)
    print(
        f"Source   : {SOURCE}"
    )
    print(
        f"Dataset  : {OUTPUT}"
    )
    print(
        f"Manifest : {MANIFEST}"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()