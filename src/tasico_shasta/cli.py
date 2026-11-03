from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tasico_shasta.config import password_context
from tasico_shasta.modeling import evaluate_dataset, sha256_file
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
    report = evaluate_dataset(
        frame,
        test_fraction=args.test_fraction,
        model_directory=args.models,
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
