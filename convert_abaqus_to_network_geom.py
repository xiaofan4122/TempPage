#!/usr/bin/env python3
"""Convert ellipse geometry CSVs between Abaqus endpoints and network parameters."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert columns like p_ox,p_oy,p_ax,p_ay,p_bx,p_by "
            "to p_ox,p_oy,p_major,p_minor,p_theta, or the reverse."
        )
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Convert network geometry CSV to Abaqus endpoint geometry CSV.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="hole_data_abaqus_geom.csv",
        help="Input geometry CSV path.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output CSV path. Defaults to hole_data_network_geom_converted.csv "
            "in forward mode and hole_data_abaqus_geom_reconstructed.csv in --reverse mode."
        ),
    )
    parser.add_argument(
        "--compare",
        help=(
            "Optional expected CSV to compare against. In forward mode this expects "
            "network geometry; in --reverse mode this expects Abaqus endpoint geometry."
        ),
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=0.5,
        help="Scale value written to generated *_scale columns in --reverse mode.",
    )
    parser.add_argument(
        "--scale-columns",
        choices=("current", "all", "none"),
        default="current",
        help=(
            "Which *_scale columns to write in --reverse mode. 'current' matches "
            "hole_data_abaqus_geom.csv: all groups except b."
        ),
    )
    parser.add_argument(
        "--exact-compare",
        action="store_true",
        help=(
            "Require theta values to match exactly. By default theta is compared "
            "modulo 180 degrees because ellipse axes are directionless."
        ),
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=1e-9,
        help="Absolute tolerance for --compare numeric checks.",
    )
    return parser.parse_args()


def ellipse_prefixes(fieldnames: list[str]) -> list[str]:
    prefixes: list[str] = []
    fields = set(fieldnames)
    for name in fieldnames:
        if not name.endswith("_ox"):
            continue
        prefix = name[: -len("_ox")]
        required = {
            f"{prefix}_oy",
            f"{prefix}_ax",
            f"{prefix}_ay",
            f"{prefix}_bx",
            f"{prefix}_by",
        }
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"prefix {prefix!r} is missing columns: {', '.join(missing)}")
        prefixes.append(prefix)
    return prefixes


def output_fieldnames(prefixes: list[str]) -> list[str]:
    names: list[str] = []
    for prefix in prefixes:
        names.extend(
            [
                f"{prefix}_ox",
                f"{prefix}_oy",
                f"{prefix}_major",
                f"{prefix}_minor",
                f"{prefix}_theta",
            ]
        )
    return names


def network_prefixes(fieldnames: list[str]) -> list[str]:
    prefixes: list[str] = []
    fields = set(fieldnames)
    for name in fieldnames:
        if not name.endswith("_ox"):
            continue
        prefix = name[: -len("_ox")]
        required = {
            f"{prefix}_oy",
            f"{prefix}_major",
            f"{prefix}_minor",
            f"{prefix}_theta",
        }
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"prefix {prefix!r} is missing columns: {', '.join(missing)}")
        prefixes.append(prefix)
    return prefixes


def scale_column_prefixes(prefixes: list[str], mode: str) -> set[str]:
    if mode == "all":
        return set(prefixes)
    if mode == "none":
        return set()
    return {prefix for prefix in prefixes if prefix != "b"}


def abaqus_output_fieldnames(prefixes: list[str], scale_prefixes: set[str]) -> list[str]:
    names: list[str] = []
    for prefix in prefixes:
        names.extend(
            [
                f"{prefix}_ox",
                f"{prefix}_oy",
                f"{prefix}_ax",
                f"{prefix}_ay",
                f"{prefix}_bx",
                f"{prefix}_by",
            ]
        )
        if prefix in scale_prefixes:
            names.append(f"{prefix}_scale")
    return names


def to_float(row: dict[str, str], name: str, row_number: int) -> float:
    try:
        return float(row[name])
    except ValueError as exc:
        raise ValueError(f"row {row_number}: column {name!r} is not numeric: {row[name]!r}") from exc


def convert_row(row: dict[str, str], prefixes: list[str], row_number: int) -> dict[str, float]:
    converted: dict[str, float] = {}
    for prefix in prefixes:
        ox = to_float(row, f"{prefix}_ox", row_number)
        oy = to_float(row, f"{prefix}_oy", row_number)
        ax = to_float(row, f"{prefix}_ax", row_number)
        ay = to_float(row, f"{prefix}_ay", row_number)
        bx = to_float(row, f"{prefix}_bx", row_number)
        by = to_float(row, f"{prefix}_by", row_number)

        a_dx = ax - ox
        a_dy = ay - oy
        b_dx = bx - ox
        b_dy = by - oy
        a_len = math.hypot(a_dx, a_dy)
        b_len = math.hypot(b_dx, b_dy)
        if a_len >= b_len:
            major = a_len
            minor = b_len
            theta = math.degrees(math.atan2(a_dy, a_dx)) % 360.0
        else:
            major = b_len
            minor = a_len
            theta = math.degrees(math.atan2(b_dy, b_dx)) % 360.0

        converted[f"{prefix}_ox"] = ox
        converted[f"{prefix}_oy"] = oy
        converted[f"{prefix}_major"] = major
        converted[f"{prefix}_minor"] = minor
        converted[f"{prefix}_theta"] = theta
    return converted


def reverse_convert_row(
    row: dict[str, str],
    prefixes: list[str],
    row_number: int,
    scale_prefixes: set[str],
    scale: float,
) -> dict[str, float]:
    converted: dict[str, float] = {}
    for prefix in prefixes:
        ox = to_float(row, f"{prefix}_ox", row_number)
        oy = to_float(row, f"{prefix}_oy", row_number)
        major = to_float(row, f"{prefix}_major", row_number)
        minor = to_float(row, f"{prefix}_minor", row_number)
        theta = math.radians(to_float(row, f"{prefix}_theta", row_number))

        major_dx = major * math.cos(theta)
        major_dy = major * math.sin(theta)
        minor_dx = -minor * math.sin(theta)
        minor_dy = minor * math.cos(theta)

        converted[f"{prefix}_ox"] = ox
        converted[f"{prefix}_oy"] = oy
        converted[f"{prefix}_ax"] = ox + major_dx
        converted[f"{prefix}_ay"] = oy + major_dy
        converted[f"{prefix}_bx"] = ox + minor_dx
        converted[f"{prefix}_by"] = oy + minor_dy
        if prefix in scale_prefixes:
            converted[f"{prefix}_scale"] = scale
    return converted


def convert_csv(input_path: Path, output_path: Path) -> tuple[list[str], int]:
    with input_path.open(newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} is empty or missing a header")

        prefixes = ellipse_prefixes(reader.fieldnames)
        if not prefixes:
            raise ValueError(f"{input_path} does not contain any *_ox geometry groups")

        fieldnames = output_fieldnames(prefixes)
        with output_path.open("w", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            row_count = 0
            for row_count, row in enumerate(reader, start=1):
                writer.writerow(convert_row(row, prefixes, row_count))

    return fieldnames, row_count


def reverse_convert_csv(
    input_path: Path,
    output_path: Path,
    scale_column_mode: str,
    scale: float,
) -> tuple[list[str], int]:
    with input_path.open(newline="") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} is empty or missing a header")

        prefixes = network_prefixes(reader.fieldnames)
        if not prefixes:
            raise ValueError(f"{input_path} does not contain any *_ox geometry groups")

        scale_prefixes = scale_column_prefixes(prefixes, scale_column_mode)
        fieldnames = abaqus_output_fieldnames(prefixes, scale_prefixes)
        with output_path.open("w", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            row_count = 0
            for row_count, row in enumerate(reader, start=1):
                writer.writerow(reverse_convert_row(row, prefixes, row_count, scale_prefixes, scale))

    return fieldnames, row_count


def angular_axis_diff(actual: float, expected: float) -> float:
    """Smallest angle difference for directionless ellipse axes."""
    return abs(((actual - expected + 90.0) % 180.0) - 90.0)


def compare_csv(actual_path: Path, expected_path: Path, tol: float, exact_theta: bool) -> None:
    with actual_path.open(newline="") as actual_file, expected_path.open(newline="") as expected_file:
        actual_reader = csv.DictReader(actual_file)
        expected_reader = csv.DictReader(expected_file)
        if actual_reader.fieldnames != expected_reader.fieldnames:
            raise ValueError(
                "header mismatch:\n"
                f"actual:   {actual_reader.fieldnames}\n"
                f"expected: {expected_reader.fieldnames}"
            )

        max_diff = 0.0
        max_location = ""
        max_axis_diff = 0.0
        max_axis_location = ""
        theta_180_flips = 0
        rows = 0
        for rows, (actual, expected) in enumerate(zip(actual_reader, expected_reader), start=1):
            for name in actual_reader.fieldnames or []:
                actual_value = float(actual[name])
                expected_value = float(expected[name])
                diff = abs(actual_value - expected_value)
                if name.endswith("_theta") and not exact_theta:
                    axis_diff = angular_axis_diff(actual_value, expected_value)
                    if axis_diff > max_axis_diff:
                        max_axis_diff = axis_diff
                        max_axis_location = f"row {rows}, column {name}"
                    exact_angle_diff = abs(((actual_value - expected_value + 180.0) % 360.0) - 180.0)
                    if exact_angle_diff > tol and axis_diff <= tol:
                        theta_180_flips += 1
                    diff = axis_diff
                if diff > max_diff:
                    max_diff = diff
                    max_location = f"row {rows}, column {name}"
                if diff > tol:
                    raise ValueError(
                        f"comparison failed at row {rows}, column {name}: "
                        f"actual={actual[name]}, expected={expected[name]}, diff={diff}"
                    )

        extra_actual = next(actual_reader, None)
        extra_expected = next(expected_reader, None)
        if extra_actual is not None or extra_expected is not None:
            raise ValueError("row count mismatch between converted and expected CSVs")

    if exact_theta:
        print(f"exact compare ok: {rows} rows, max_diff={max_diff:.3g} at {max_location or 'n/a'}")
    else:
        print(
            "axis-equivalent compare ok: "
            f"{rows} rows, max_diff={max_diff:.3g} at {max_location or 'n/a'}, "
            f"max_axis_diff={max_axis_diff:.3g} at {max_axis_location or 'n/a'}, "
            f"theta_180_flips={theta_180_flips}"
        )


def compare_abaqus_csv(actual_path: Path, expected_path: Path, tol: float) -> None:
    actual_tmp = actual_path.with_suffix(actual_path.suffix + ".network_compare_tmp.csv")
    expected_tmp = expected_path.with_suffix(expected_path.suffix + ".network_compare_tmp.csv")
    try:
        convert_csv(actual_path, actual_tmp)
        convert_csv(expected_path, expected_tmp)
        compare_csv(actual_tmp, expected_tmp, tol, exact_theta=False)
    finally:
        for path in (actual_tmp, expected_tmp):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(
        args.output
        or (
            "hole_data_abaqus_geom_reconstructed.csv"
            if args.reverse
            else "hole_data_network_geom_converted.csv"
        )
    )

    if args.reverse:
        fieldnames, row_count = reverse_convert_csv(input_path, output_path, args.scale_columns, args.scale)
    else:
        fieldnames, row_count = convert_csv(input_path, output_path)
    print(f"wrote {output_path} with {row_count} rows and {len(fieldnames)} columns")

    if args.compare:
        if args.reverse:
            compare_abaqus_csv(output_path, Path(args.compare), args.tol)
        else:
            compare_csv(output_path, Path(args.compare), args.tol, args.exact_compare)


if __name__ == "__main__":
    main()
