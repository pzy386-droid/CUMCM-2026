"""Production tests for 附件1 reading and time alignment (no reference answers)."""
import datetime as dt

import numpy as np
import pytest
from openpyxl import Workbook

from microgrid.inputs import (
    EXPECTED_HEADERS, InputError, Q1Input, hhmm, load_attachment1, parse_endpoint_minutes,
)

ROOT_INPUT = "data/raw/附件1.xlsx"


@pytest.mark.parametrize("value,expected", [
    (dt.time(0, 10), 10),
    (dt.time(23, 50), 1430),
    (dt.datetime(1900, 1, 1, 10, 10), 610),
    ("10:10", 610),
    ("00:10", 10),
    ("9:00", 540),
    ("24:00", 1440),
    ("0:00+1", 1440),
    (" 0:00+1 ", 1440),
    ("0：10", 10),
])
def test_parse_endpoint_minutes(value, expected):
    assert parse_endpoint_minutes(value) == expected


@pytest.mark.parametrize("value", ["25:00", "10:60", "abc", "0:10+2", "24:10", 610, None, True,
                                   dt.time(0, 10, 30)])
def test_parse_endpoint_rejects(value):
    with pytest.raises(InputError):
        parse_endpoint_minutes(value)


def test_hhmm_formatting():
    assert hhmm(0) == "00:00"
    assert hhmm(10) == "00:10"
    assert hhmm(600) == "10:00"
    assert hhmm(1440) == "24:00"


def test_real_input_alignment():
    data = load_attachment1(ROOT_INPUT)
    assert data.slots == 144
    assert data.interval_minutes == 10
    assert data.start_label(1) == "00:00" and data.end_label(1) == "00:10"
    assert data.start_label(144) == "23:50" and data.end_label(144) == "24:00"
    # table-1 slots: 10:00-10:10 is slot 61, i.e. input Excel row 62
    assert data.start_label(61) == "10:00" and data.end_label(61) == "10:10"
    assert int(data.input_excel_rows[60]) == 62
    for slot, start in zip([61, 73, 85, 97, 109, 121], ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]):
        assert data.start_label(slot) == start
    assert np.all(data.price > 0) and np.all(data.load_kw >= 0) and np.all(data.pv_kw >= 0)
    assert len(data.sha256) == 64


def _write_workbook(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(EXPECTED_HEADERS)
    for row in rows:
        ws.append(row)
    wb.save(path)


def _synthetic_rows(n=144):
    rows = []
    for i in range(1, n + 1):
        minutes = 10 * i
        label = "0:00+1" if minutes == 1440 else f"{minutes // 60}:{minutes % 60:02d}"
        rows.append([label, 0.5, 1000.0, 0.0])
    return rows


def test_synthetic_string_labels(tmp_path):
    path = tmp_path / "in.xlsx"
    _write_workbook(path, _synthetic_rows())
    data = load_attachment1(path)
    assert isinstance(data, Q1Input)
    assert data.end_label(144) == "24:00"


def test_misaligned_timestamp_rejected(tmp_path):
    rows = _synthetic_rows()
    rows[5][0] = "1:10"   # slot 6 must end at 1:00
    path = tmp_path / "in.xlsx"
    _write_workbook(path, rows)
    with pytest.raises(InputError, match="expected right endpoint"):
        load_attachment1(path)


def test_wrong_row_count_and_header(tmp_path):
    path = tmp_path / "in.xlsx"
    _write_workbook(path, _synthetic_rows()[:-1])
    with pytest.raises(InputError, match="rows"):
        load_attachment1(path)
    wb = Workbook()
    ws = wb.active
    ws.append(["time", "price", "load", "pv"])
    for row in _synthetic_rows():
        ws.append(row)
    wb.save(path)
    with pytest.raises(InputError, match="header"):
        load_attachment1(path)


def test_nonpositive_price_rejected(tmp_path):
    rows = _synthetic_rows()
    rows[0][1] = 0.0
    path = tmp_path / "in.xlsx"
    _write_workbook(path, rows)
    with pytest.raises(InputError, match="positive"):
        load_attachment1(path)
