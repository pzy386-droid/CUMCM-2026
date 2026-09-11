"""Figures for Q1, drawn from the exported ledger only (never from a re-solve).

Two stacked panels share one time axis; no dual y-axes:
  schedule.png  — (a) price; (b) load, PV, grid purchase as power (kW);
                  (c) storage charge (+) / discharge (−) bars in kWh per slot.
  soc.png       — stored energy S_t (kWh) with the 1200/10800 bounds and the
                  initial/terminal 6000 kWh markers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

COLORS = {          # fixed categorical assignment (slot order), never cycled
    "load": "#2a78d6",      # blue
    "pv": "#eb6834",        # orange
    "grid": "#1baf7a",      # aqua
    "charge": "#eda100",    # yellow
    "discharge": "#4a3aa7", # violet
    "price": "#52514e",     # secondary ink
    "soc": "#2a78d6",
    "bound": "#c3c2b7",
}


def _hours(rows: list[dict[str, Any]]) -> np.ndarray:
    """Slot start time in hours (0 ... 23.833)."""
    return np.array([int(r["start"][:2]) + int(r["start"][3:]) / 60 for r in rows])


def _style(ax):
    ax.grid(True, axis="y", color="#e6e5e1", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#c3c2b7")
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e", labelsize=8)


def write_figures(out_dir: Path, rows: list[dict[str, Any]], params, delta_hours: float) -> list[str]:
    """Write schedule.png and soc.png; returns the file names written."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    cjk = [name for name in ("Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "SimHei",
                             "PingFang SC", "Microsoft YaHei", "Source Han Sans SC")
           if any(f.name == name for f in font_manager.fontManager.ttflist)]
    plt.rcParams["font.family"] = ["sans-serif"]
    plt.rcParams["font.sans-serif"] = cjk + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t = _hours(rows)
    width = delta_hours
    price = np.array([r["price_yuan_per_kwh"] for r in rows])
    load = np.array([r["load_kw"] for r in rows])
    pv = np.array([r["pv_kw"] for r in rows])
    grid_kw = np.array([r["grid_kwh"] for r in rows]) / delta_hours
    charge = np.array([r["charge_kwh"] for r in rows])
    discharge = np.array([r["discharge_kwh"] for r in rows])
    soc = np.array([rows[0]["soc_start_kwh"], *[r["soc_end_kwh"] for r in rows]])
    ticks = np.arange(0, 25, 2)

    fig, axes = plt.subplots(3, 1, figsize=(9, 8.2), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1.6, 1.2], "hspace": 0.32})
    ax = axes[0]
    ax.step(t, price, where="post", color=COLORS["price"], linewidth=1.6)
    ax.set_ylabel("电价 (元/kWh)", fontsize=9)
    ax.set_title("问题1 日前计划：电价、功率平衡与储能充放电", fontsize=11, color="#0b0b0b", pad=10)
    _style(ax)

    ax = axes[1]
    ax.step(t, load, where="post", color=COLORS["load"], linewidth=1.8, label="小区负载 (kW)")
    ax.step(t, pv, where="post", color=COLORS["pv"], linewidth=1.8, label="光伏预测功率 (kW)")
    ax.step(t, grid_kw, where="post", color=COLORS["grid"], linewidth=1.8, label="计划购电功率 (kW，购电量/Δt)")
    ax.set_ylabel("功率 (kW)", fontsize=9)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8, frameon=False, ncol=3)
    _style(ax)

    ax = axes[2]
    ax.bar(t, charge, width=width, align="edge", color=COLORS["charge"], linewidth=0, label="充电量 c_t (kWh，母线侧，+)")
    ax.bar(t, -discharge, width=width, align="edge", color=COLORS["discharge"], linewidth=0, label="放电量 d_t (kWh，母线侧，−)")
    ax.axhline(0, color="#c3c2b7", linewidth=0.8)
    ax.set_ylabel("每10分钟电量 (kWh)", fontsize=9)
    ax.set_xlabel("时间 (h)，每段10分钟，0:00–24:00", fontsize=9)
    ax.set_xlim(0, 24)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{int(h):02d}:00" for h in ticks])
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8, frameon=False, ncol=2)
    _style(ax)
    fig.savefig(out_dir / "schedule.png", dpi=200, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    edges = np.append(t, 24.0)
    ax.plot(edges, soc, color=COLORS["soc"], linewidth=2.0, label="储电量 S_t (kWh)")
    ax.axhline(params.soc_max_kwh, color=COLORS["bound"], linewidth=1.0, linestyle="--")
    ax.axhline(params.soc_min_kwh, color=COLORS["bound"], linewidth=1.0, linestyle="--")
    ax.text(24.1, params.soc_max_kwh, f"上限 {params.soc_max_kwh:.0f}", fontsize=8, va="center", color="#52514e")
    ax.text(24.1, params.soc_min_kwh, f"下限 {params.soc_min_kwh:.0f}", fontsize=8, va="center", color="#52514e")
    ax.scatter([0, 24], [soc[0], soc[-1]], s=36, color=COLORS["soc"], zorder=3)
    ax.annotate(f"0:00  {soc[0]:.0f} kWh", (0, soc[0]), textcoords="offset points", xytext=(6, 10),
                fontsize=8, color="#0b0b0b")
    ax.annotate(f"24:00  {soc[-1]:.0f} kWh", (24, soc[-1]), textcoords="offset points", xytext=(-80, 10),
                fontsize=8, color="#0b0b0b")
    ax.set_xlim(0, 24)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{int(h):02d}:00" for h in ticks])
    ax.set_ylim(0, params.soc_max_kwh * 1.12)
    ax.set_xlabel("时间 (h)", fontsize=9)
    ax.set_ylabel("储电量 (kWh)", fontsize=9)
    ax.set_title("问题1 储能储电量轨迹（S_t = S_(t-1) + 0.9c_t − d_t/0.9）", fontsize=11, color="#0b0b0b")
    _style(ax)
    fig.savefig(out_dir / "soc.png", dpi=200, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)
    return ["schedule.png", "soc.png"]
