"""Production tests for the Q1 MILP: physics, efficiency, boundaries, exclusivity, failure handling."""
import numpy as np
import pytest

from microgrid.inputs import Q1Input, load_attachment1
from microgrid.model_q1 import (
    ENERGY_TOL_KWH, Q1Params, SolveError, build_milp, check_solution, solve_q1,
)

ROOT_INPUT = "data/raw/附件1.xlsx"


def synthetic(price, load_kw, pv_kw, interval_minutes):
    n = len(price)
    assert n * interval_minutes == 1440
    return Q1Input(path="synthetic", sha256="0" * 64, interval_minutes=interval_minutes,
                   price=np.array(price, float), load_kw=np.array(load_kw, float),
                   pv_kw=np.array(pv_kw, float),
                   end_minutes=np.arange(1, n + 1) * interval_minutes,
                   input_excel_rows=np.arange(2, n + 2))


@pytest.fixture(scope="module")
def real_data():
    return load_attachment1(ROOT_INPUT)


@pytest.fixture(scope="module")
def real_params():
    return Q1Params()


@pytest.fixture(scope="module")
def real_solution(real_data, real_params):
    return solve_q1(real_data, real_params)


def test_four_slot_arbitrage_with_efficiency():
    # 4 slots of 6 h: cheap 0.1, dear 1.0, cheap 0.2, dear 1.0; storage 1200..10800 from/to 6000.
    # Unique optimum: fill to 10800 in slot 1, serve the whole 6000 kWh load from storage in
    # slot 2, refill in slot 3, discharge exactly what returns the state to 6000 in slot 4.
    data = synthetic([0.1, 1.0, 0.2, 1.0], [1000] * 4, [0] * 4, 360)
    params = Q1Params(interval_minutes=360, max_charge_kw=5000, max_discharge_kw=5000)
    sol = solve_q1(data, params)
    c1 = 4800 / 0.9
    s2 = 10800 - 6000 / 0.9
    c3 = (10800 - s2) / 0.9
    d4 = 4800 * 0.9
    assert sol.charge_kwh[0] == pytest.approx(c1, abs=1e-6)
    assert sol.discharge_kwh[1] == pytest.approx(6000, abs=1e-6)
    assert sol.charge_kwh[2] == pytest.approx(c3, abs=1e-6)
    assert sol.discharge_kwh[3] == pytest.approx(d4, abs=1e-6)
    assert sol.soc_kwh[1] == pytest.approx(10800, abs=1e-6)
    assert sol.soc_kwh[2] == pytest.approx(s2, abs=1e-6)
    assert sol.soc_kwh[0] == 6000 and sol.soc_kwh[-1] == pytest.approx(6000, abs=1e-6)
    expected = 0.1 * (6000 + c1) + 0.2 * (6000 + c3) + 1.0 * (6000 - d4)
    assert sol.objective_yuan == pytest.approx(expected, rel=1e-9)
    assert sol.solver["status"] == "optimal" and sol.solver["mip_gap"] <= 1e-8


def test_unit_efficiency_changes_energy_not_state():
    data = synthetic([0.1, 1.0, 0.2, 1.0], [1000] * 4, [0] * 4, 360)
    params = Q1Params(interval_minutes=360, charge_efficiency=1.0, discharge_efficiency=1.0)
    sol = solve_q1(data, params)
    assert sol.charge_kwh[0] == pytest.approx(4800, abs=1e-6)
    assert sol.discharge_kwh[1] == pytest.approx(6000, abs=1e-6)
    assert sol.charge_kwh[2] == pytest.approx(6000, abs=1e-6)
    assert sol.discharge_kwh[3] == pytest.approx(4800, abs=1e-6)
    assert sol.objective_yuan == pytest.approx(0.1 * 10800 + 0.2 * 12000 + 1200, rel=1e-9)


def test_kw_to_kwh_conversion_in_balance():
    data = synthetic([1.0] * 144, [600.0] * 144, [0.0] * 144, 10)
    sol = solve_q1(data, Q1Params())
    # constant price and no PV: no reason to cycle; grid equals load energy 600 kW × 1/6 h
    assert np.allclose(sol.grid_kwh, 100.0, atol=1e-6)
    assert sol.objective_yuan == pytest.approx(144 * 100.0, rel=1e-9)


def test_surplus_pv_is_spilled_only_in_charge_mode():
    price = [0.5] * 144
    load = [500.0] * 144
    pv = [0.0] * 144
    for t in range(60, 84):      # 10:00-14:00 massive PV
        pv[t] = 40000.0
    data = synthetic(price, load, pv, 10)
    sol = solve_q1(data, Q1Params())
    assert sol.spill_kwh.sum() > 0
    assert np.all((sol.spill_kwh <= ENERGY_TOL_KWH) | (sol.discharge_kwh <= ENERGY_TOL_KWH))
    assert np.all(sol.mode[sol.spill_kwh > ENERGY_TOL_KWH] > 0.5)
    assert np.all(sol.grid_kwh[60:84] <= ENERGY_TOL_KWH)


def test_real_instance_physics(real_data, real_params, real_solution):
    sol = real_solution
    n = real_data.slots
    delta = real_params.delta_hours
    assert sol.soc_kwh.shape == (n + 1,)
    assert sol.soc_kwh[0] == pytest.approx(6000, abs=ENERGY_TOL_KWH)
    assert sol.soc_kwh[-1] == pytest.approx(6000, abs=ENERGY_TOL_KWH)
    assert sol.soc_kwh.min() >= 1200 - ENERGY_TOL_KWH and sol.soc_kwh.max() <= 10800 + ENERGY_TOL_KWH
    assert sol.charge_kwh.max() <= 5000 / 6 + ENERGY_TOL_KWH
    assert sol.discharge_kwh.max() <= 5000 / 6 + ENERGY_TOL_KWH
    dyn = sol.soc_kwh[1:] - sol.soc_kwh[:-1] - 0.9 * sol.charge_kwh + sol.discharge_kwh / 0.9
    assert np.max(np.abs(dyn)) <= ENERGY_TOL_KWH
    bal = sol.grid_kwh + real_data.pv_kw * delta + sol.discharge_kwh \
        - real_data.load_kw * delta - sol.charge_kwh - sol.spill_kwh
    assert np.max(np.abs(bal)) <= ENERGY_TOL_KWH
    assert np.max(np.minimum(sol.charge_kwh, sol.discharge_kwh)) <= ENERGY_TOL_KWH
    assert np.max(np.minimum(sol.discharge_kwh, sol.spill_kwh)) <= ENERGY_TOL_KWH
    assert np.all(np.isclose(sol.mode, np.round(sol.mode), atol=1e-6))
    assert sol.objective_yuan == pytest.approx(float(real_data.price @ sol.grid_kwh), rel=1e-9)
    assert sol.solver["status"] == "optimal" and 0 <= sol.solver["mip_gap"] <= 1e-8


def test_real_instance_beats_no_storage(real_data, real_params, real_solution):
    delta = real_params.delta_hours
    no_storage = float(real_data.price @ np.maximum((real_data.load_kw - real_data.pv_kw) * delta, 0))
    assert real_solution.objective_yuan < no_storage


def test_milp_structure_enforces_exclusivity(real_data, real_params):
    m = build_milp(real_data, real_params)
    n = real_data.slots
    x = np.zeros(m.objective.size)
    x[m.index["s"]] = 6000
    A = m.constraints.A
    # charge and discharge together at slot 0 with either mode value is infeasible
    for z in (0.0, 1.0):
        x[m.index["c"].start] = 100.0
        x[m.index["d"].start] = 100.0
        x[m.index["z"].start] = z
        residual = A @ x
        violated = (residual < m.constraints.lb - 1e-9) | (residual > m.constraints.ub + 1e-9)
        assert violated[2 * n] or violated[3 * n]
    # discharge together with spill is infeasible for both modes
    x[m.index["c"].start] = 0.0
    x[m.index["r"].start] = 5.0
    for z in (0.0, 1.0):
        x[m.index["z"].start] = z
        residual = A @ x
        violated = (residual < m.constraints.lb - 1e-9) | (residual > m.constraints.ub + 1e-9)
        assert violated[3 * n] or violated[4 * n]
    assert m.integrality[m.index["z"]].all() and not m.integrality[: 5 * n + 1].any()


def test_self_check_rejects_broken_solution(real_data, real_params, real_solution):
    import copy
    bad = copy.deepcopy(real_solution)
    bad.soc_kwh[10] += 1.0
    with pytest.raises(SolveError, match="SOC dynamics"):
        check_solution(real_data, real_params, bad)
    bad = copy.deepcopy(real_solution)
    bad.charge_kwh[0] = 1.0
    bad.discharge_kwh[0] = 1.0
    with pytest.raises(SolveError):
        check_solution(real_data, real_params, bad)


def test_infeasible_parameters_fail_closed(real_data):
    with pytest.raises(SolveError) as info:
        solve_q1(real_data, Q1Params(initial_soc_kwh=20000))
    assert info.value.info["status"] == "infeasible"
    with pytest.raises(SolveError):
        solve_q1(real_data, Q1Params(initial_soc_kwh=1200, terminal_soc_kwh=10800, max_charge_kw=1.0))


def test_parameter_validation():
    with pytest.raises(ValueError):
        Q1Params(charge_efficiency=1.5).validate()
    with pytest.raises(ValueError):
        Q1Params(interval_minutes=7).validate()
    with pytest.raises(ValueError):
        Q1Params.from_config({"soc_min_kwh": 5000, "soc_max_kwh": 4000})
