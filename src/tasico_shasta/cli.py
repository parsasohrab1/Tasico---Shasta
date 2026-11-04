from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tasico_shasta.config import password_context
from tasico_shasta.modeling import TARGET_COLUMNS, evaluate_dataset, sha256_file
from tasico_shasta.optimization import backtest_savings


def main() -> None:
    parser = argparse.ArgumentParser(prog="tasico")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("hash-password", help="prompt for a password and print its bcrypt hash")
    evaluate = commands.add_parser("evaluate", help="train and evaluate using a chronological CSV holdout")
    evaluate.add_argument("--input", required=True, type=Path)
    evaluate.add_argument("--report", required=True, type=Path)
    evaluate.add_argument("--models", type=Path)
    evaluate.add_argument("--test-fraction", type=float, default=0.2)
    evaluate.add_argument(
        "--target-column",
        help="evaluate only this target column instead of all standard targets",
    )
    evaluate.add_argument(
        "--timestamp-column",
        default="timestamp",
        help="source column containing timestamps (default: timestamp)",
    )
    evaluate.add_argument(
        "--timestamp-format",
        help="explicit pandas datetime format for the source timestamp column",
    )
    evaluate.add_argument(
        "--factory-id",
        help="factory identifier to assign when the CSV has no factory_id column",
    )
    evaluate.add_argument(
        "--samples-per-hour",
        type=int,
        default=1,
        help="sampling frequency used for daily/weekly features (default: 1)",
    )

    savings = commands.add_parser(
        "backtest-savings", help="compare measured holdout bills with modeled dispatch cost"
    )
    savings.add_argument("--input", required=True, type=Path)
    savings.add_argument("--equipment", required=True, type=Path)
    savings.add_argument("--report", required=True, type=Path)
    savings.add_argument("--interval-hours", type=float, default=1.0)

    args = parser.parse_args()
    if args.command == "hash-password":
        password = getpass.getpass("Password: ")
        password_bytes = len(password.encode("utf-8"))
        if not 12 <= password_bytes <= 72:
            parser.error("password must be between 12 and 72 UTF-8 bytes")
        print(password_context.hash(password))
        return
    if args.command == "evaluate":
        _evaluate(args)
        return
    if args.command == "backtest-savings":
        _backtest_savings(args)


def _evaluate(args: argparse.Namespace) -> None:
    frame = pd.read_csv(args.input)
    if args.timestamp_column not in frame.columns:
        raise ValueError(f"timestamp column {args.timestamp_column!r} is missing")
    if args.timestamp_column != "timestamp":
        if "timestamp" in frame.columns:
            raise ValueError("CSV contains both 'timestamp' and the selected timestamp column")
        frame = frame.rename(columns={args.timestamp_column: "timestamp"})
    if args.timestamp_format:
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            format=args.timestamp_format,
            errors="raise",
        )
    if "factory_id" not in frame.columns:
        frame["factory_id"] = args.factory_id or args.input.stem
    elif args.factory_id:
        raise ValueError("--factory-id can only be used when the CSV has no factory_id column")

    targets = [args.target_column] if args.target_column else TARGET_COLUMNS
    report = evaluate_dataset(
        frame,
        test_fraction=args.test_fraction,
        model_directory=args.models,
        target_columns=targets,
        samples_per_hour=args.samples_per_hour,
    )
    report["dataset_sha256"] = sha256_file(args.input)
    report["dataset_path"] = args.input.name
    _write_json(args.report, report)


def _backtest_savings(args: argparse.Namespace) -> None:
    frame = pd.read_csv(args.input)
    with args.equipment.open(encoding="utf-8") as source:
        equipment = json.load(source)
    if not isinstance(equipment, dict):
        raise ValueError("equipment file must contain an object keyed by factory_id")
    report = backtest_savings(
        cast(list[dict[str, Any]], frame.to_dict(orient="records")),
        equipment,
        interval_hours=args.interval_hours,
    )
    report["dataset_sha256"] = sha256_file(args.input)
    report["dataset_path"] = args.input.name
    _write_json(args.report, report)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, indent=2, ensure_ascii=False, allow_nan=False)
        destination.write("\n")


if __name__ == "__main__":
    main()
