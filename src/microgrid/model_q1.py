"""Q1 deterministic day-ahead scheduling MILP (docs/q1_spec.md).

Decision variables per slot t = 1..N (all energies in kWh, bus side):
  g_t  grid purchase          c_t charge drawn from the bus
  d_t  discharge to the bus   r_t surplus energy left unused
  S_t  stored energy after slot t (S_0 given)
  z_t  binary mode: 1 = charge/surplus allowed, 0 = discharge allowed
Constraints:
  g_t + q_t + d_t = l_t + c_t + r_t          (q = PV·Δ, l = load·Δ)
  S_t = S_{t-1} + η_c c_t − d_t / η_d
  S_min ≤ S_t ≤ S_max,  S_0 = S_init,  S_N = S_term
  0 ≤ c_t ≤ M_c z_t,  0 ≤ d_t ≤ M_d (1 − z_t),  0 ≤ r_t ≤ R_t z_t
  0 ≤ g_t ≤ G_t = l_t + M_c,  R_t = G_t + q_t
Objective: minimise Σ p_t g_t.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import sparse
from scipy.optimize import Bounds, LinearConstraint, milp

from .inputs import Q1Input

ENERGY_TOL_KWH = 1e-6      # energy balance / SOC residual tolerance (spec)
COST_ABS_TOL_YUAN = 1e-5   # cost comparison tolerance floor (spec)
COST_REL_TOL = 1e-8

# scipy.optimize.milp status codes
_STATUS_TEXT = {0: "optimal", 1: "iteration_or_time_limit", 2: "infeasible",
                3: "unbounded", 4: "other"}


class SolveError(RuntimeError):
    """Raised when the MILP does not return a proven optimal solution."""

    def __init__(self, message: str, info: dict[str, Any] | None = None):
        super().__init__(message)
        self.info = info or {}


@dataclass(frozen=True)
class Q1Params:
    interval_minutes: int = 10
    soc_min_kwh: float = 1200.0
    soc_max_kwh: float = 10800.0
    initial_soc_kwh: float = 6000.0
    terminal_soc_kwh: float = 6000.0
    max_charge_kw: float = 5000.0
    max_discharge_kw: float = 5000.0
    charge_efficiency: float = 0.9
    discharge_efficiency: float = 0.9
    mip_rel_gap: float = 1e-9
    time_limit_seconds: float = 120.0

    @property
    def delta_hours(self) -> float:
        return self.interval_minutes / 60.0

    @property
    def max_charge_kwh(self) -> float:
        return self.max_charge_kw * self.delta_hours

    @property
    def max_discharge_kwh(self) -> float:
        return self.max_discharge_kw * self.delta_hours

    def validate(self) -> None:
        if self.interval_minutes <= 0 or 1440 % self.interval_minutes:
            raise ValueError("interval_minutes must divide 1440")
        if not 0 < self.charge_efficiency <= 1 or not 0 < self.discharge_efficiency <= 1:
            raise ValueError("efficiencies must lie in (0, 1]")
        if self.soc_min_kwh > self.soc_max_kwh:
            raise ValueError("soc_min_kwh exceeds soc_max_kwh")
        if self.max_charge_kw < 0 or self.max_discharge_kw < 0:
            raise ValueError("negative power limits")
        if not 0 <= self.mip_rel_gap < 1:
            raise ValueError("mip_rel_gap must lie in [0, 1)")
        if self.time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be positive")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Q1Params":
        keys = {f: config[f] for f in cls.__dataclass_fields__ if f in config}
        params = cls(**keys)
        params.validate()
        return params


@dataclass
class Q1Solution:
    grid_kwh: np.ndarray
    charge_kwh: np.ndarray
    discharge_kwh: np.ndarray
    spill_kwh: np.ndarray
    soc_kwh: np.ndarray            # shape (N+1,), soc_kwh[0] = S_0
    mode: np.ndarray               # z_t, shape (N,)
    objective_yuan: float
    solver: dict[str, Any]
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class MilpData:
    objective: np.ndarray
    constraints: LinearConstraint
    bounds: Bounds
    integrality: np.ndarray
    index: dict[str, slice]
    n_slots: int


def build_milp(data: Q1Input, params: Q1Params) -> MilpData:
    """Assemble the sparse MILP. Variable order: g, c, d, r, S(0..N), z."""
    params.validate()
    n = data.slots
    if data.interval_minutes != params.interval_minutes:
        raise ValueError("input interval does not match parameters")
    delta = params.delta_hours
    load = data.load_kw * delta
    pv = data.pv_kw * delta
    m_c = params.max_charge_kwh
    m_d = params.max_discharge_kwh
    g_max = load + m_c
    r_max = g_max + pv

    g, c, d, r = 0, n, 2 * n, 3 * n
    s, z = 4 * n, 5 * n + 1
    total = 6 * n + 1
    index = {"g": slice(g, g + n), "c": slice(c, c + n), "d": slice(d, d + n),
             "r": slice(r, r + n), "s": slice(s, s + n + 1), "z": slice(z, z + n)}

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []

    def put(i, j, v):
        rows.append(i)
        cols.append(j)
        vals.append(float(v))

    lb = np.zeros(5 * n)
    ub = np.zeros(5 * n)
    for t in range(n):
        # energy balance: g + d - c - r = load - pv
        i = t
        put(i, g + t, 1.0)
        put(i, d + t, 1.0)
        put(i, c + t, -1.0)
        put(i, r + t, -1.0)
        lb[i] = ub[i] = load[t] - pv[t]
        # dynamics: S_t - S_{t-1} - eta_c c + d / eta_d = 0
        i = n + t
        put(i, s + t + 1, 1.0)
        put(i, s + t, -1.0)
        put(i, c + t, -params.charge_efficiency)
        put(i, d + t, 1.0 / params.discharge_efficiency)
        lb[i] = ub[i] = 0.0
        # c - M_c z <= 0
        i = 2 * n + t
        put(i, c + t, 1.0)
        put(i, z + t, -m_c)
        lb[i], ub[i] = -np.inf, 0.0
        # d + M_d z <= M_d
        i = 3 * n + t
        put(i, d + t, 1.0)
        put(i, z + t, m_d)
        lb[i], ub[i] = -np.inf, m_d
        # r - R z <= 0
        i = 4 * n + t
        put(i, r + t, 1.0)
        put(i, z + t, -r_max[t])
        lb[i], ub[i] = -np.inf, 0.0
    matrix = sparse.csr_matrix((vals, (rows, cols)), shape=(5 * n, total))

    var_lb = np.zeros(total)
    var_ub = np.zeros(total)
    var_lb[index["g"]], var_ub[index["g"]] = 0.0, g_max
    var_lb[index["c"]], var_ub[index["c"]] = 0.0, m_c
    var_lb[index["d"]], var_ub[index["d"]] = 0.0, m_d
    var_lb[index["r"]], var_ub[index["r"]] = 0.0, r_max
    var_lb[index["s"]], var_ub[index["s"]] = params.soc_min_kwh, params.soc_max_kwh
    var_lb[s], var_ub[s] = params.initial_soc_kwh, params.initial_soc_kwh
    var_lb[s + n], var_ub[s + n] = params.terminal_soc_kwh, params.terminal_soc_kwh
    var_lb[index["z"]], var_ub[index["z"]] = 0.0, 1.0

    objective = np.zeros(total)
    objective[index["g"]] = data.price
    integrality = np.zeros(total, dtype=int)
    integrality[index["z"]] = 1
    return MilpData(objective=objective, constraints=LinearConstraint(matrix, lb, ub),
                    bounds=Bounds(var_lb, var_ub), integrality=integrality,
                    index=index, n_slots=n)


def solve_q1(data: Q1Input, params: Q1Params) -> Q1Solution:
    """Solve the MILP with HiGHS via scipy.optimize.milp; fail closed if not optimal."""
    milp_data = build_milp(data, params)
    options = {"disp": False, "mip_rel_gap": params.mip_rel_gap,
               "time_limit": params.time_limit_seconds, "presolve": True}
    start = time.perf_counter()
    result = milp(milp_data.objective, constraints=milp_data.constraints,
                  bounds=milp_data.bounds, integrality=milp_data.integrality,
                  options=options)
    wall = time.perf_counter() - start
    status_code = int(result.status)
    info = {
        "name": "scipy.optimize.milp (HiGHS)",
        "status": _STATUS_TEXT.get(status_code, "other"),
        "status_code": status_code,
        "success": bool(result.success),
        "message": str(result.message),
        "wall_seconds": wall,
        "mip_gap": _finite_or_none(getattr(result, "mip_gap", None)),
        "mip_dual_bound": _finite_or_none(getattr(result, "mip_dual_bound", None)),
        "mip_node_count": _int_or_none(getattr(result, "mip_node_count", None)),
        "options": options,
    }
    if status_code != 0 or not result.success or result.x is None:
        raise SolveError(f"MILP did not reach proven optimality: status={status_code} "
                         f"({info['status']}): {result.message}", info)
    gap = info["mip_gap"]
    if gap is None or not (0 <= gap <= max(params.mip_rel_gap, 1e-8)):
        raise SolveError(f"MILP gap {gap!r} not within tolerance", info)
    x = np.asarray(result.x, dtype=float)
    idx = milp_data.index
    solution = Q1Solution(
        grid_kwh=x[idx["g"]].copy(), charge_kwh=x[idx["c"]].copy(),
        discharge_kwh=x[idx["d"]].copy(), spill_kwh=x[idx["r"]].copy(),
        soc_kwh=x[idx["s"]].copy(), mode=x[idx["z"]].copy(),
        objective_yuan=float(result.fun), solver=info,
    )
    solution.diagnostics = check_solution(data, params, solution)
    return solution


def _finite_or_none(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _int_or_none(value):
    return None if value is None else int(value)


def check_solution(data: Q1Input, params: Q1Params, sol: Q1Solution,
                   tol: float = ENERGY_TOL_KWH) -> dict[str, Any]:
    """Production self-check of physical feasibility; raises SolveError on violation."""
    n = data.slots
    delta = params.delta_hours
    load = data.load_kw * delta
    pv = data.pv_kw * delta
    g, c, d, r, s = sol.grid_kwh, sol.charge_kwh, sol.discharge_kwh, sol.spill_kwh, sol.soc_kwh
    arrays = {"grid": g, "charge": c, "discharge": d, "spill": r, "soc": s}
    for name, arr in arrays.items():
        if arr.shape[0] != (n + 1 if name == "soc" else n) or not np.all(np.isfinite(arr)):
            raise SolveError(f"{name}: wrong shape or non-finite values")
    energy = g + pv + d - load - c - r
    dynamics = s[1:] - s[:-1] - params.charge_efficiency * c + d / params.discharge_efficiency
    checks = {
        "max_energy_residual_kwh": float(np.max(np.abs(energy))),
        "max_soc_residual_kwh": float(np.max(np.abs(dynamics))),
        "min_decision_kwh": float(min(g.min(), c.min(), d.min(), r.min())),
        "max_charge_kwh": float(c.max()),
        "max_discharge_kwh": float(d.max()),
        "min_soc_kwh": float(s.min()),
        "max_soc_kwh": float(s.max()),
        "soc_initial_kwh": float(s[0]),
        "soc_final_kwh": float(s[-1]),
        "max_simultaneous_charge_discharge_kwh": float(np.max(np.minimum(c, d))),
        "max_discharge_with_spill_kwh": float(np.max(np.minimum(d, r))),
        "objective_recomputed_yuan": float(data.price @ g),
    }
    failures = []
    if checks["max_energy_residual_kwh"] > tol:
        failures.append("energy balance")
    if checks["max_soc_residual_kwh"] > tol:
        failures.append("SOC dynamics")
    if checks["min_decision_kwh"] < -tol:
        failures.append("negative decision")
    if checks["max_charge_kwh"] > params.max_charge_kwh + tol:
        failures.append("charge power")
    if checks["max_discharge_kwh"] > params.max_discharge_kwh + tol:
        failures.append("discharge power")
    if checks["min_soc_kwh"] < params.soc_min_kwh - tol or checks["max_soc_kwh"] > params.soc_max_kwh + tol:
        failures.append("SOC bounds")
    if abs(s[0] - params.initial_soc_kwh) > tol or abs(s[-1] - params.terminal_soc_kwh) > tol:
        failures.append("initial/terminal SOC")
    if checks["max_simultaneous_charge_discharge_kwh"] > tol:
        failures.append("simultaneous charge and discharge")
    if checks["max_discharge_with_spill_kwh"] > tol:
        failures.append("discharge with surplus spill")
    cost_tol = max(COST_ABS_TOL_YUAN, COST_REL_TOL * abs(sol.objective_yuan))
    if abs(checks["objective_recomputed_yuan"] - sol.objective_yuan) > cost_tol:
        failures.append("objective mismatch")
    if failures:
        raise SolveError("solution self-check failed: " + ", ".join(failures), checks)
    checks["tolerance_kwh"] = tol
    checks["cost_tolerance_yuan"] = cost_tol
    return checks
