"""Q1 command line entry point.

    python -m microgrid.q1 --config configs/q1.json --output outputs/q1

Reads 附件1, solves the locked Q1 MILP once, and writes every deliverable from
that single per-slot ledger: schedule.csv, summary.json, result1.xlsx,
template_mapping.csv, tables_q1.md and run_metadata.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy
import openpyxl
import scipy

from . import export_q1 as ex
from .inputs import InputError, load_attachment1, sha256_file
from .model_q1 import ENERGY_TOL_KWH, Q1Params, SolveError, solve_q1

SCHEMA_VERSION = 1
REQUIRED_CONFIG = {
    "settlement_side": "bus",
    "timestamp_interpretation": "right_endpoint_representative",
    "template_mode": "corrected_semantic",
}


class ConfigError(ValueError):
    pass


def find_repo_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def git_state(root: Path | None) -> tuple[str | None, bool | None]:
    """Return (HEAD commit, dirty flag) or (None, None) without git.

    Dirty means any modified, staged or untracked file under the model code paths
    (src/, configs/, pyproject.toml, requirements-lock.txt); output folders do not count.
    """
    if root is None:
        return None, None
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--",
                                 "src", "configs", "pyproject.toml", "requirements-lock.txt"],
                                cwd=root, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return head, bool(status.strip())


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError(f"config schema_version must be {SCHEMA_VERSION}")
    for key, expected in REQUIRED_CONFIG.items():
        if config.get(key) != expected:
            raise ConfigError(f"config {key}={config.get(key)!r} is not the locked value {expected!r}")
    for key in ("input", "template", "slots", "interval_minutes"):
        if key not in config:
            raise ConfigError(f"config missing {key}")
    if config["nominal_capacity_kwh"] < config["soc_max_kwh"]:
        raise ConfigError("soc_max_kwh exceeds nominal capacity")
    return config


def check_manifest(root: Path | None, rel_path: str, digest: str) -> None:
    """Fail closed if data/manifest.json lists the file with a different hash."""
    if root is None:
        return
    manifest = root / "data" / "manifest.json"
    if not manifest.is_file():
        return
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in doc.get("files", []):
        if Path(entry["path"]).as_posix() == Path(rel_path).as_posix() and entry["sha256"] != digest:
            raise InputError(f"{rel_path} hash {digest} differs from data/manifest.json")


def run(config_path: Path, output_dir: Path, argv: list[str] | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    config_path = Path(config_path)
    config = load_config(config_path)
    root = find_repo_root(config_path.resolve().parent)
    base = root if root is not None else Path.cwd()
    input_path = base / config["input"]
    template_path = base / config["template"]
    params = Q1Params.from_config(config)

    data = load_attachment1(input_path, slots=int(config["slots"]),
                            interval_minutes=int(config["interval_minutes"]))
    template_hash = sha256_file(template_path)
    check_manifest(root, config["input"], data.sha256)
    check_manifest(root, config["template"], template_hash)

    solution = solve_q1(data, params)
    rows = ex.build_ledger(data, solution)
    totals = ex.ledger_totals(rows)
    commit, dirty = git_state(root)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ex.write_schedule_csv(output_dir / "schedule.csv", rows)
    mapping = ex.template_mapping(template_path, rows)
    ex.write_template_mapping_csv(output_dir / "template_mapping.csv", mapping)
    ex.write_result1_xlsx(template_path, output_dir / "result1.xlsx", rows, params)
    ex.write_tables_md(output_dir / "tables_q1.md", rows, totals)
    if sha256_file(template_path) != template_hash:
        raise ex.ExportError("template file changed during export")

    solver = {
        "name": solution.solver["name"],
        "status": solution.solver["status"],
        "mip_gap": solution.solver["mip_gap"],
        "wall_seconds": solution.solver["wall_seconds"],
        "mip_dual_bound_yuan": solution.solver["mip_dual_bound"],
        "mip_node_count": solution.solver["mip_node_count"],
        "message": solution.solver["message"],
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        **totals,
        "objective_solver_yuan": solution.objective_yuan,
        "input_sha256": data.sha256,
        "template_sha256": template_hash,
        "solver": solver,
        "source_git_commit": commit,
        "source_dirty": dirty,
        "selected_intervals": ex.selected_intervals(rows),
        "four_hour_storage": ex.four_hour_blocks(rows),
        "self_check": solution.diagnostics,
        "mode_slots_charge_or_spill": int(round(float(solution.mode.sum()))),
    }
    ex.write_json(output_dir / "summary.json", summary)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "command": "python -m microgrid.q1 " + " ".join(argv if argv is not None else sys.argv[1:]),
        "started_utc": started,
        "elapsed_seconds": time.perf_counter() - t0,
        "solver_wall_seconds": solution.solver["wall_seconds"],
        "config_path": str(config_path),
        "config": config,
        "parameters": {
            "delta_hours": params.delta_hours,
            "max_charge_kwh_per_slot": params.max_charge_kwh,
            "max_discharge_kwh_per_slot": params.max_discharge_kwh,
            "charge_efficiency": params.charge_efficiency,
            "discharge_efficiency": params.discharge_efficiency,
            "soc_bounds_kwh": [params.soc_min_kwh, params.soc_max_kwh],
            "initial_terminal_soc_kwh": [params.initial_soc_kwh, params.terminal_soc_kwh],
        },
        "solver_options": solution.solver["options"],
        "solver_raw": {k: solution.solver[k] for k in ("status_code", "success", "message",
                                                       "mip_gap", "mip_dual_bound", "mip_node_count")},
        "numerical_tolerances": {
            "energy_and_soc_residual_kwh": ENERGY_TOL_KWH,
            "cost_tolerance_yuan": solution.diagnostics.get("cost_tolerance_yuan"),
            "mip_rel_gap_requested": params.mip_rel_gap,
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "openpyxl": openpyxl.__version__,
            "platform": platform.platform(),
        },
        "source_git_commit": commit,
        "source_dirty": dirty,
        "input_path": config["input"],
        "template_path": config["template"],
        "outputs": ["schedule.csv", "summary.json", "result1.xlsx",
                    "template_mapping.csv", "tables_q1.md", "run_metadata.json"],
    }
    ex.write_json(output_dir / "run_metadata.json", metadata)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Solve CUMCM 2026 C Q1 and export deliverables.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = run(args.config, args.output, argv=list(argv) if argv is not None else sys.argv[1:])
    except (ConfigError, InputError, SolveError, ex.ExportError) as exc:
        print(f"Q1 run failed: {exc}", file=sys.stderr)
        info = getattr(exc, "info", None)
        if info:
            print(json.dumps(info, ensure_ascii=False, indent=2, default=str), file=sys.stderr)
        return 1
    print(json.dumps({k: summary[k] for k in (
        "objective_yuan", "total_grid_kwh", "total_charge_kwh", "total_discharge_kwh",
        "total_spill_kwh", "soc_initial_kwh", "soc_final_kwh", "solver", "source_git_commit",
        "source_dirty")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
