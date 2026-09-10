"""Compute an independent LP lower bound, never an official result1.xlsx."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import numpy
import scipy

from q1_audit import ROOT, read_input, sha256, solve_reference, write_records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"review/artifacts/q1_reference.json")
    args = parser.parse_args()
    values = read_input()
    certificate, records = solve_reference(values)
    certificate["input_sha256"] = sha256(ROOT/"data/raw/附件1.xlsx")
    certificate["versions"] = {"python": platform.python_version(),
                               "numpy": numpy.__version__, "scipy": scipy.__version__}
    certificate["selected_intervals"] = [
        {"slot": records[i-1]["slot"], "interval": f"{records[i-1]['start']}-{records[i-1]['end']}",
         "grid_kwh": records[i-1]["grid_kwh"]} for i in [61, 73, 85, 97, 109, 121]
    ]
    certificate["four_hour_storage"] = [
        {"interval": f"{4*b:02d}:00-{4*b+4:02d}:00",
         "charge_kwh": sum(r["charge_kwh"] for r in records[24*b:24*(b+1)]),
         "discharge_kwh": sum(r["discharge_kwh"] for r in records[24*b:24*(b+1)])}
        for b in range(6)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(certificate, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
                           encoding="utf-8")
    write_records(args.output.with_suffix(".csv"), records)
    print(json.dumps(certificate, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
