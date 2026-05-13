#!/usr/bin/env python3
"""Core stress-strain curve calculations for the curve inspector.

This module owns the classification logic. The HTML inspector should load the
JSON produced here and only handle visualization.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable, Sequence


LINEAR_CV = 0.24
TREND_TH = 0.22
VALLEY_PROM = 0.20
NEG_TH = -0.10
MAX_STRAIN = 0.1


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def std(values: Sequence[float]) -> float:
    m = mean(values)
    return math.sqrt(mean([(value - m) * (value - m) for value in values]))


def finite_only(values: Iterable[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def segment_mean(values: Sequence[float], start_frac: float, end_frac: float) -> float:
    n = len(values)
    i0 = max(0, math.floor(start_frac * n))
    i1 = min(n, math.ceil(end_frac * n))
    return mean(values[i0 : max(i0 + 1, i1)])


def linear_slope(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0

    sx = sy = sxx = sxy = 0.0
    for i, y in enumerate(values):
        x = i / (n - 1)
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y

    den = n * sxx - sx * sx
    return 0.0 if abs(den) < 1e-12 else (n * sxy - sx * sy) / den


def raw_finite_difference(stress: Sequence[float], d_eps: float) -> list[float]:
    n = len(stress)
    if n < 2:
        return []

    stiffness = [0.0] * n
    for i in range(n):
        if i == 0:
            stiffness[i] = (stress[1] - stress[0]) / d_eps
        elif i == n - 1:
            stiffness[i] = (stress[n - 1] - stress[n - 2]) / d_eps
        else:
            stiffness[i] = (stress[i + 1] - stress[i - 1]) / (2.0 * d_eps)
    return stiffness


def empty_features(stress: Sequence[float]) -> dict[str, object]:
    return {
        "type": "linear",
        "k": [],
        "eps": [],
        "cv": 0.0,
        "trend": 0.0,
        "trendDelta": 0.0,
        "valleyProminence": 0.0,
        "valleyPos": 0.0,
        "signChanges": 0,
        "kStart": 0.0,
        "kEnd": 0.0,
        "kMin": 0.0,
        "kMax": 0.0,
        "minIdx": 0,
        "finalStress": float(stress[-1]) if stress else 0.0,
        "maxStress": max(stress) if stress else 0.0,
    }


def compute_curve_features(stress: Sequence[float], max_strain: float = MAX_STRAIN) -> dict[str, object]:
    y = [float(value) for value in stress]
    n = len(y)
    if n < 8:
        return empty_features(y)

    d_eps = max_strain / (n - 1)
    eps = [i * d_eps for i in range(n)]
    k = raw_finite_difference(y, d_eps)

    m = len(k)
    i_a = max(0, math.floor(0.02 * m))
    i_b = min(m, math.ceil(0.98 * m))
    kt = k[i_a:i_b]

    k_start = segment_mean(k, 0.05, 0.20)
    k_end = segment_mean(k, 0.80, 0.95)
    k_mean_abs = max(mean([abs(value) for value in kt]), 1e-12)
    cv = std(kt) / k_mean_abs
    trend = linear_slope(kt) / k_mean_abs
    k_min = min(kt)
    k_max = max(kt)
    k_range = max(k_max - k_min, k_mean_abs, 1e-12)

    min_local_idx = min(range(len(kt)), key=kt.__getitem__)
    left = kt[: max(1, min_local_idx)]
    right = kt[min(len(kt) - 1, min_local_idx + 1) :]
    left_high = max(left) if left else kt[min_local_idx]
    right_high = max(right) if right else kt[min_local_idx]
    left_drop = (left_high - kt[min_local_idx]) / k_range
    right_recovery = (right_high - kt[min_local_idx]) / k_range
    valley_prominence = min(left_drop, right_recovery)
    valley_pos = (min_local_idx + i_a) / max(m - 1, 1)

    sign_changes = 0
    prev = 0
    dk_tol = 0.015 * k_range
    for i in range(i_a + 1, i_b):
        dk = k[i] - k[i - 1]
        sg = 1 if dk > dk_tol else (-1 if dk < -dk_tol else 0)
        if sg != 0:
            if prev != 0 and sg != prev:
                sign_changes += 1
            prev = sg

    trend_delta = (k_end - k_start) / max(abs(k_start), abs(k_end), k_mean_abs, 1e-12)
    has_interior_valley = 0.10 < valley_pos < 0.90 and valley_prominence > VALLEY_PROM
    has_recovery = right_recovery > VALLEY_PROM and k_end > k_min + 0.18 * k_range

    curve_type = "linear"
    if has_interior_valley and has_recovery and sign_changes >= 1:
        curve_type = "s-type"
    elif (
        k_min < NEG_TH * max(abs(k_max), k_mean_abs, 1e-12)
        or trend_delta < -TREND_TH
        or trend < -TREND_TH
    ):
        curve_type = "decreasing"
    elif trend_delta > TREND_TH or trend > TREND_TH:
        curve_type = "increasing"
    elif cv < LINEAR_CV:
        curve_type = "linear"
    else:
        curve_type = "increasing" if trend_delta >= 0 else "decreasing"

    return {
        "type": curve_type,
        "k": k,
        "eps": eps,
        "cv": cv,
        "trend": trend,
        "trendDelta": trend_delta,
        "valleyProminence": valley_prominence,
        "valleyPos": valley_pos,
        "signChanges": sign_changes,
        "kStart": k_start,
        "kEnd": k_end,
        "kMin": k_min,
        "kMax": k_max,
        "minIdx": min_local_idx + i_a,
        "finalStress": y[-1],
        "maxStress": max(y),
    }


def classify_curve(stress: Sequence[float], max_strain: float = MAX_STRAIN) -> str:
    return str(compute_curve_features(stress, max_strain=max_strain)["type"])


def parse_numeric_csv(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open(newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row_number, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue
            try:
                rows.append([float(cell.strip()) for cell in row])
            except ValueError as exc:
                raise ValueError(f"{path}: row {row_number} contains a non-numeric value") from exc
    return rows


def classify_rows(rows: Sequence[Sequence[float]], max_strain: float = MAX_STRAIN) -> list[dict[str, object]]:
    feature_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        features = compute_curve_features(row, max_strain=max_strain)
        features["index"] = index
        feature_rows.append(features)
    return feature_rows


def write_features_json(
    y_csv_path: Path,
    output_path: Path,
    max_strain: float = MAX_STRAIN,
) -> list[dict[str, object]]:
    rows = parse_numeric_csv(y_csv_path)
    feature_rows = classify_rows(rows, max_strain=max_strain)
    payload = {
        "schema": "curve-inspector-features-v1",
        "source": str(y_csv_path),
        "maxStrain": max_strain,
        "rowCount": len(feature_rows),
        "rows": feature_rows,
    }
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, separators=(",", ":"))
    return feature_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate curve-inspector feature JSON from a Y_DATA CSV.")
    parser.add_argument("y_csv", help="Stress-strain Y_DATA CSV.")
    parser.add_argument(
        "-o",
        "--output",
        default="curve_features.json",
        help="Output feature JSON path.",
    )
    parser.add_argument(
        "--max-strain",
        type=float,
        default=MAX_STRAIN,
        help="Final nominal strain represented by each curve row.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    feature_rows = write_features_json(Path(args.y_csv), Path(args.output), max_strain=args.max_strain)
    counts: dict[str, int] = {}
    for row in feature_rows:
        curve_type = str(row["type"])
        counts[curve_type] = counts.get(curve_type, 0) + 1
    summary = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    print(f"wrote {args.output} with {len(feature_rows)} rows ({summary})")


if __name__ == "__main__":
    main()
