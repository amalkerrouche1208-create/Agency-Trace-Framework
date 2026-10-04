from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sklearn.metrics import adjusted_rand_score

from agencytrace.ml.clustering import (
    fit_labels,
)


@dataclass(frozen=True, slots=True)
class FeatureDropResult:
    k: int
    removed_feature: str
    retained_feature_count: int
    ari_vs_primary: float


def evaluate_feature_drop_robustness(
    x: np.ndarray,
    feature_names: tuple[str, ...],
    *,
    k: int,
    random_state: int = 42,
) -> list[FeatureDropResult]:
    """
    Evaluate how much a K-means solution changes when each
    feature is removed in turn.

    The clustering fitted on the complete feature matrix is
    treated as the reference partition. Agreement between the
    reference and each reduced-feature partition is measured
    with Adjusted Rand Index (ARI).
    """

    if x.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if x.shape[1] != len(
        feature_names
    ):
        raise ValueError(
            "Feature-name count does not match "
            "matrix column count."
        )

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Feature matrix contains non-finite values."
        )

    primary_labels, _, _ = fit_labels(
        x,
        algorithm="kmeans",
        k=k,
        random_state=random_state,
    )

    results: list[
        FeatureDropResult
    ] = []

    for index, feature in enumerate(
        feature_names
    ):
        reduced = np.delete(
            x,
            index,
            axis=1,
        )

        labels, _, _ = fit_labels(
            reduced,
            algorithm="kmeans",
            k=k,
            random_state=random_state,
        )

        ari = adjusted_rand_score(
            primary_labels,
            labels,
        )

        results.append(
            FeatureDropResult(
                k=k,
                removed_feature=feature,
                retained_feature_count=(
                    reduced.shape[1]
                ),
                ari_vs_primary=float(
                    ari
                ),
            )
        )

    return results


def standard_scale(
    x: np.ndarray,
) -> np.ndarray:
    """
    Standardize each feature using mean and population
    standard deviation.

    Features with zero variance are centered but not divided
    by zero.
    """

    if x.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Feature matrix contains non-finite values."
        )

    means = np.mean(
        x,
        axis=0,
    )

    stds = np.std(
        x,
        axis=0,
        ddof=0,
    )

    safe_stds = np.where(
        stds == 0,
        1.0,
        stds,
    )

    return (
        x - means
    ) / safe_stds


def robust_scale(
    x: np.ndarray,
) -> np.ndarray:
    """
    Robust-scale each feature using its median and
    interquartile range (IQR).

    This mirrors the preprocessing used by the primary
    AgencyTrace clustering matrix.

    Features with zero IQR are centered but are not divided
    by zero.
    """

    if x.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Feature matrix contains non-finite values."
        )

    medians = np.median(
        x,
        axis=0,
    )

    q1 = np.quantile(
        x,
        0.25,
        axis=0,
    )

    q3 = np.quantile(
        x,
        0.75,
        axis=0,
    )

    iqrs = q3 - q1

    safe_iqrs = np.where(
        iqrs == 0,
        1.0,
        iqrs,
    )

    return (
        x - medians
    ) / safe_iqrs


def compare_scalings(
    raw_x: np.ndarray,
    reference_labels: np.ndarray,
    *,
    k: int,
    random_state: int = 42,
) -> list[dict[str, object]]:
    """
    Refit K-means under alternative scaling specifications
    and compare each partition with an existing reference
    partition using ARI.
    """

    if raw_x.ndim != 2:
        raise ValueError(
            "Expected a 2-D raw feature matrix."
        )

    if len(reference_labels) != len(
        raw_x
    ):
        raise ValueError(
            "Reference-label count does not match "
            "the number of matrix rows."
        )

    variants = {
        "robust": robust_scale(
            raw_x
        ),
        "standard": standard_scale(
            raw_x
        ),
    }

    results: list[
        dict[str, object]
    ] = []

    for name, matrix in variants.items():
        labels, _, _ = fit_labels(
            matrix,
            algorithm="kmeans",
            k=k,
            random_state=random_state,
        )

        ari = adjusted_rand_score(
            reference_labels,
            labels,
        )

        results.append(
            {
                "k": k,
                "scaling": name,
                "ari_vs_primary": float(
                    ari
                ),
            }
        )

    return results