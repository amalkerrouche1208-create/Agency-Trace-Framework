from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from sklearn.cluster import (
    AgglomerativeClustering,
    KMeans,
)
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture


Algorithm = Literal[
    "kmeans",
    "ward",
    "gmm",
]


@dataclass(frozen=True, slots=True)
class MatrixData:
    session_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    values: np.ndarray


@dataclass(frozen=True, slots=True)
class ClusterEvaluation:
    algorithm: str
    k: int

    silhouette: float
    calinski_harabasz: float
    davies_bouldin: float

    stability_ari_mean: float
    stability_ari_std: float

    min_cluster_size: int
    max_cluster_size: int
    min_cluster_fraction: float
    max_cluster_fraction: float

    aic: float | None = None
    bic: float | None = None


def load_scaled_matrix(
    path: Path,
) -> MatrixData:
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if (
            reader.fieldnames is None
            or "session_id"
            not in reader.fieldnames
        ):
            raise ValueError(
                "Expected a session_id column."
            )

        feature_names = tuple(
            name
            for name in reader.fieldnames
            if name != "session_id"
        )

        session_ids: list[str] = []
        values: list[list[float]] = []

        for row in reader:
            session_ids.append(
                row["session_id"]
            )

            values.append(
                [
                    float(row[name])
                    for name in feature_names
                ]
            )

    matrix = np.asarray(
        values,
        dtype=float,
    )

    if matrix.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if not np.all(
        np.isfinite(matrix)
    ):
        raise ValueError(
            "Scaled matrix contains "
            "non-finite values."
        )

    return MatrixData(
        session_ids=tuple(
            session_ids
        ),
        feature_names=feature_names,
        values=matrix,
    )


def fit_labels(
    x: np.ndarray,
    *,
    algorithm: Algorithm,
    k: int,
    random_state: int = 42,
) -> tuple[
    np.ndarray,
    float | None,
    float | None,
]:
    if k < 2:
        raise ValueError(
            "k must be >= 2."
        )

    if k >= len(x):
        raise ValueError(
            "k must be smaller than "
            "the number of samples."
        )

    if algorithm == "kmeans":
        model = KMeans(
            n_clusters=k,
            n_init=20,
            random_state=random_state,
        )

        labels = model.fit_predict(x)

        return (
            labels,
            None,
            None,
        )

    if algorithm == "ward":
        model = AgglomerativeClustering(
            n_clusters=k,
            linkage="ward",
        )

        labels = model.fit_predict(x)

        return (
            labels,
            None,
            None,
        )

    if algorithm == "gmm":
        model = GaussianMixture(
            n_components=k,
            covariance_type="full",
            n_init=5,
            max_iter=500,
            reg_covar=1e-6,
            random_state=random_state,
        )

        labels = model.fit_predict(x)

        return (
            labels,
            float(model.aic(x)),
            float(model.bic(x)),
        )

    raise ValueError(
        f"Unknown algorithm: {algorithm}"
    )


def cluster_sizes(
    labels: np.ndarray,
) -> dict[int, int]:
    unique, counts = np.unique(
        labels,
        return_counts=True,
    )

    return {
        int(label): int(count)
        for label, count
        in zip(
            unique,
            counts,
            strict=True,
        )
    }


def subsample_stability(
    x: np.ndarray,
    reference_labels: np.ndarray,
    *,
    algorithm: Algorithm,
    k: int,
    repeats: int = 40,
    sample_fraction: float = 0.80,
    random_state: int = 42,
) -> tuple[float, float]:
    if not (
        0.0
        < sample_fraction
        <= 1.0
    ):
        raise ValueError(
            "sample_fraction must be "
            "in (0, 1]."
        )

    if repeats < 1:
        raise ValueError(
            "repeats must be >= 1."
        )

    rng = np.random.default_rng(
        random_state
    )

    sample_size = max(
        k + 1,
        int(
            round(
                len(x)
                * sample_fraction
            )
        ),
    )

    scores: list[float] = []

    for repeat in range(repeats):
        indices = rng.choice(
            len(x),
            size=sample_size,
            replace=False,
        )

        subset = x[indices]

        labels, _, _ = fit_labels(
            subset,
            algorithm=algorithm,
            k=k,
            random_state=(
                random_state
                + repeat
                + 1
            ),
        )

        score = adjusted_rand_score(
            reference_labels[
                indices
            ],
            labels,
        )

        scores.append(
            float(score)
        )

    return (
        float(np.mean(scores)),
        float(np.std(scores)),
    )


def evaluate_candidate(
    x: np.ndarray,
    *,
    algorithm: Algorithm,
    k: int,
    stability_repeats: int = 40,
    stability_fraction: float = 0.80,
    random_state: int = 42,
) -> tuple[
    ClusterEvaluation,
    np.ndarray,
]:
    labels, aic, bic = fit_labels(
        x,
        algorithm=algorithm,
        k=k,
        random_state=random_state,
    )

    unique = np.unique(labels)

    if len(unique) < 2:
        raise RuntimeError(
            "Clustering produced fewer "
            "than two clusters."
        )

    sizes = cluster_sizes(
        labels
    )

    minimum = min(
        sizes.values()
    )

    maximum = max(
        sizes.values()
    )

    stability_mean, stability_std = (
        subsample_stability(
            x,
            labels,
            algorithm=algorithm,
            k=k,
            repeats=stability_repeats,
            sample_fraction=(
                stability_fraction
            ),
            random_state=(
                random_state
            ),
        )
    )

    evaluation = ClusterEvaluation(
        algorithm=algorithm,
        k=k,
        silhouette=float(
            silhouette_score(
                x,
                labels,
            )
        ),
        calinski_harabasz=float(
            calinski_harabasz_score(
                x,
                labels,
            )
        ),
        davies_bouldin=float(
            davies_bouldin_score(
                x,
                labels,
            )
        ),
        stability_ari_mean=(
            stability_mean
        ),
        stability_ari_std=(
            stability_std
        ),
        min_cluster_size=minimum,
        max_cluster_size=maximum,
        min_cluster_fraction=(
            minimum / len(x)
        ),
        max_cluster_fraction=(
            maximum / len(x)
        ),
        aic=aic,
        bic=bic,
    )

    return (
        evaluation,
        labels,
    )


def fit_pca(
    x: np.ndarray,
    *,
    feature_names: tuple[str, ...],
) -> tuple[
    PCA,
    np.ndarray,
]:
    pca = PCA()

    scores = pca.fit_transform(
        x
    )

    if (
        pca.components_.shape[1]
        != len(feature_names)
    ):
        raise RuntimeError(
            "PCA feature count mismatch."
        )

    return (
        pca,
        scores,
    )