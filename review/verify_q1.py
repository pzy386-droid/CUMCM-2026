"""Fail-closed audit of fable's Q1 run, independent of its model implementation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from q1_audit import (
    ROOT, check_mapping, check_optimal_cost, check_records, check_summary,
    check_workbook, read_input, read_records, require, solve_reference, verify_manifest,
)


def verify(run):
    run = Path(run)
    hashes = verify_manifest()
    values = read_input()
    for name in ["schedule.csv", "summary.json", "result1.xlsx",
                 "template_mapping.csv", "tables_q1.md"]:
        require((run/name).is_file(), f"missing required output: {name}")
    records = read_records(run/"schedule.csv")
    metrics = check_records(records, values)
    check_summary(run/"summary.json", metrics, hashes)
    check_workbook(run/"result1.xlsx", records)
    check_mapping(run/"template_mapping.csv", records)
    reference, _ = solve_reference(values)
    check_optimal_cost(metrics["objective_yuan"], reference["objective_yuan"])
    return {
        "status": "passed",
        "scope": "automated physical, accounting, provenance, workbook, mapping and LP-bound checks",
        "manual_review_pending": ["production code", "tables_q1.md contents", "figures", "clean environment reproduction"],
        "metrics": metrics,
        "independent_lp_bound_yuan": reference["objective_yuan"],
        "gap_to_lp_bound_yuan": metrics["objective_yuan"]-reference["objective_yuan"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.run)
        code = 0
    except Exception as exc:
        report = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
        code = 1
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text+"\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
