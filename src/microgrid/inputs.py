"""Reading and time alignment of 附件1 for Q1.

Time convention (docs/q1_spec.md): every timestamp in the input sheet is the
right endpoint of the preceding ten-minute interval, and the value in that row
is the representative power of that interval.  Input row 2 (first data row)
is slot 1 = 00:00-00:10; input row 62 is slot 61 = 10:00-10:10.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from openpyxl import load_workbook

EXPECTED_HEADERS = ["时间", "电价", "小区负载", "光伏发电预测功率"]


class InputError(ValueError):
    """Raised when 附件1 does not match the locked Q1 specification."""


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_endpoint_minutes(value) -> int:
    """Return minutes after 00:00 of the current day for an input time label.

    Accepts ``datetime.time`` (00:10 ... 23:50), ``datetime.datetime`` with a
    zero date component, and strings such as ``"10:10"``, ``"00:10"``,
    ``"24:00"`` or ``"0:00+1"`` (``+1`` marks the following day, i.e. 24:00).
    """
    if isinstance(value, bool):
        raise InputError(f"invalid time label: {value!r}")
    if isinstance(value, dt.datetime):
        if value.second or value.microsecond:
            raise InputError(f"time label has seconds: {value!r}")
        return value.hour * 60 + value.minute
    if isinstance(value, dt.time):
        if value.second or value.microsecond:
            raise InputError(f"time label has seconds: {value!r}")
        return value.hour * 60 + value.minute
    if isinstance(value, str):
        text = value.strip().replace("：", ":")
        extra = 0
        if text.endswith("+1"):
            text = text[:-2].strip()
            extra = 1440
        pieces = text.split(":")
        if len(pieces) != 2 or not all(p.strip().isdigit() for p in pieces):
            raise InputError(f"invalid time label: {value!r}")
        hour, minute = int(pieces[0]), int(pieces[1])
        if not (0 <= hour <= 24 and 0 <= minute < 60) or (hour == 24 and minute != 0):
            raise InputError(f"time label out of range: {value!r}")
        minutes = hour * 60 + minute + extra
        if minutes > 1440:
            raise InputError(f"time label beyond 24:00: {value!r}")
        return minutes
    raise InputError(f"unsupported time label type {type(value).__name__}: {value!r}")


def hhmm(minutes: int) -> str:
    """Format minutes after midnight as HH:MM; 1440 renders as 24:00."""
    if not 0 <= minutes <= 1440:
        raise ValueError(f"minutes out of range: {minutes}")
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _number(value, label: str) -> float:
    if isinstance(value, bool) or value is None:
        raise InputError(f"{label}: expected a number, got {value!r}")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise InputError(f"{label}: expected a number, got {value!r}") from None
    if not math.isfinite(result):
        raise InputError(f"{label}: non-finite value {value!r}")
    return result


@dataclass(frozen=True)
class Q1Input:
    path: str
    sha256: str
    interval_minutes: int
    price: np.ndarray          # yuan/kWh, shape (N,)
    load_kw: np.ndarray        # kW, shape (N,)
    pv_kw: np.ndarray          # kW, shape (N,)
    end_minutes: np.ndarray    # right endpoint of each slot, minutes, shape (N,)
    input_excel_rows: np.ndarray  # 1-based Excel row of each slot, shape (N,)

    @property
    def slots(self) -> int:
        return int(self.price.shape[0])

    @property
    def start_minutes(self) -> np.ndarray:
        return self.end_minutes - self.interval_minutes

    def start_label(self, slot: int) -> str:
        return hhmm(int(self.start_minutes[slot - 1]))

    def end_label(self, slot: int) -> str:
        return hhmm(int(self.end_minutes[slot - 1]))


def load_attachment1(path: Path | str, slots: int = 144, interval_minutes: int = 10) -> Q1Input:
    """Read 附件1 and align it to the internal slot axis (slot 1 = 00:00-00:10)."""
    path = Path(path)
    if not path.is_file():
        raise InputError(f"input file not found: {path}")
    if slots * interval_minutes != 1440:
        raise InputError("slots × interval_minutes must cover exactly one day")
    wb = load_workbook(path, read_only=True, data_only=False)
    try:
        if len(wb.worksheets) != 1:
            raise InputError(f"expected one worksheet, found {len(wb.worksheets)}")
        rows = [list(row) for row in wb.worksheets[0].values]
    finally:
        wb.close()
    # drop fully empty trailing rows that read_only mode can report
    while rows and all(v is None for v in rows[-1]):
        rows.pop()
    if len(rows) != slots + 1:
        raise InputError(f"expected {slots + 1} rows (header + {slots}), found {len(rows)}")
    header = [str(v).strip() if v is not None else "" for v in rows[0][:4]]
    if header != EXPECTED_HEADERS:
        raise InputError(f"unexpected header {header}, expected {EXPECTED_HEADERS}")
    price = np.zeros(slots)
    load = np.zeros(slots)
    pv = np.zeros(slots)
    ends = np.zeros(slots, dtype=int)
    for i in range(slots):
        row = rows[i + 1]
        excel_row = i + 2
        if len(row) < 4:
            raise InputError(f"row {excel_row}: fewer than four columns")
        minutes = parse_endpoint_minutes(row[0])
        expected = (i + 1) * interval_minutes
        if minutes != expected:
            raise InputError(
                f"row {excel_row}: time label {row[0]!r} = {minutes} min, expected right endpoint "
                f"{hhmm(expected)} for slot {i + 1}")
        ends[i] = minutes
        price[i] = _number(row[1], f"row {excel_row} 电价")
        load[i] = _number(row[2], f"row {excel_row} 小区负载")
        pv[i] = _number(row[3], f"row {excel_row} 光伏发电预测功率")
    if np.any(price <= 0):
        raise InputError("Q1 model assumes strictly positive prices")
    if np.any(load < 0) or np.any(pv < 0):
        raise InputError("negative load or PV power in input")
    return Q1Input(
        path=str(path), sha256=sha256_file(path), interval_minutes=interval_minutes,
        price=price, load_kw=load, pv_kw=pv, end_minutes=ends,
        input_excel_rows=np.arange(2, slots + 2),
    )
