#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Header-row detection tests for the Table chunker (rag.app.table).

Regression guard for a silent data-loss bug. ``_looks_like_header`` treats any
non-ASCII text as a header marker, which is true of every Chinese cell - header
or data. Combined with ``header_like_cells >= data_like_cells``, an all-Chinese
data row was classified as a header row, and nothing capped how deep the header
was allowed to grow. A cable spec sheet with a merged header therefore lost
every data row.
"""

from __future__ import annotations

import importlib
import sys
import warnings

# Importing rag.app.table pulls api -> rag.llm -> deepdoc -> xgboost; xgboost may warn on
# pkg_resources in a way that breaks its compat shim unless pkg_resources loads first.
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*", category=UserWarning)
import pkg_resources  # noqa: F401 — stabilize xgboost import during collection

import pytest
from openpyxl import Workbook

_PARSER_PREFIX = "deepdoc.parser"


def _snapshot_parser_modules():
    return {name: sys.modules[name] for name in list(sys.modules) if name == _PARSER_PREFIX or name.startswith(f"{_PARSER_PREFIX}.")}


def _restore_parser_modules(saved):
    for name in [name for name in list(sys.modules) if name == _PARSER_PREFIX or name.startswith(f"{_PARSER_PREFIX}.")]:
        del sys.modules[name]
    sys.modules.update(saved)


@pytest.fixture(scope="module")
def excel():
    """Load rag.app.table against the real deepdoc.parser package.

    test/unit_test/rag/conftest.py swaps in a bare deepdoc.parser.pdf_parser stub
    (RAGFlowPdfParser only) so rag.nlp can import without the deepdoc stack, but
    table.Excel subclasses deepdoc.parser.ExcelParser. Swap the real package in for
    the import only, then restore the previous state so sibling rag tests keep the
    lightweight stub they were written against.
    """
    saved = _snapshot_parser_modules()
    for name in list(saved):
        del sys.modules[name]
    importlib.invalidate_caches()
    try:
        module = importlib.import_module("rag.app.table")
        if not hasattr(module.Excel, "_load_excel_to_workbook"):
            module = importlib.reload(module)
    finally:
        _restore_parser_modules(saved)
    return module


def _parse(excel, ws):
    """Mirror Excel.__call__: detect the header rows, then slice off the data."""
    rows = excel.Excel._get_rows_limited(ws)
    parser = excel.Excel()
    headers, header_rows = parser._parse_headers(ws, rows)
    data = [[cell.value for cell in row] for row in rows[header_rows:]]
    return headers, header_rows, data


def _two_level_merged_sheet():
    """Vertical merges A1:A2 / D1:D2 plus one horizontal B1:C1 merge."""
    wb = Workbook()
    ws = wb.active
    ws.append(["型号", "规格", None, "备注"])
    ws.append([None, "内径", "外径", None])
    ws.append(["YJV22", "10", "20", "合格"])
    ws.append(["YJV32", "15", "25", "合格"])
    ws.merge_cells("A1:A2")
    ws.merge_cells("B1:C1")
    ws.merge_cells("D1:D2")
    return ws


def _merged_chinese_sheet(data_rows):
    """A horizontal-only merge: structurally a single header row."""
    wb = Workbook()
    ws = wb.active
    ws.append(["型号", "材料", None])
    for row in data_rows:
        ws.append(row)
    ws.merge_cells("B1:C1")
    return ws


def test_merged_two_level_header_keeps_every_data_row(excel):
    # Scenario A: merged multi-level header over rows that contain numbers.
    headers, header_rows, data = _parse(excel, _two_level_merged_sheet())

    assert header_rows == 2
    assert headers == ["型号", "规格-内径", "规格-外径", "备注"]
    assert data == [
        ["YJV22", "10", "20", "合格"],
        ["YJV32", "15", "25", "合格"],
    ]


def test_merged_header_does_not_swallow_an_all_chinese_data_row(excel):
    # Scenario B: every cell is Chinese, so the content heuristic alone reads the
    # data row as a second header row. The merge spans one row only, which is the
    # structural evidence that caps the header at one row.
    ws = _merged_chinese_sheet([["YJV22", "交联聚乙烯", "铜芯"]])

    _, header_rows, data = _parse(excel, ws)

    assert header_rows == 1
    assert data == [["YJV22", "交联聚乙烯", "铜芯"]]


def test_merged_header_does_not_swallow_multiple_all_chinese_rows(excel):
    rows = [
        ["YJV22", "交联聚乙烯", "铜芯"],
        ["YJV32", "聚氯乙烯", "铝芯"],
        ["KVV", "橡胶", "铜芯"],
    ]

    _, header_rows, data = _parse(excel, _merged_chinese_sheet(rows))

    assert header_rows == 1
    assert data == rows


def test_data_directly_under_a_horizontal_merge_is_kept(excel):
    wb = Workbook()
    ws = wb.active
    ws.append(["规格", None, "备注"])
    ws.append(["2.5mm2", "4mm2", "ok"])
    ws.merge_cells("A1:B1")

    _, header_rows, data = _parse(excel, ws)

    assert header_rows == 1
    assert data == [["2.5mm2", "4mm2", "ok"]]


def test_vertical_merges_still_allow_a_three_level_header(excel):
    # The merged-cell bound must not cap a legitimately deep header.
    wb = Workbook()
    ws = wb.active
    ws.append(["电缆", "规格", "尺寸", "备注"])
    ws.append([None, "额定", "外径", None])
    ws.append([None, "电压", "偏差", None])
    ws.merge_cells("A1:A3")
    ws.merge_cells("D1:D3")
    ws.append(["YJV", "10", "20", "ok"])
    ws.append(["KVV", "5", "8", "ok"])

    headers, header_rows, data = _parse(excel, ws)

    assert header_rows == 3
    assert headers == ["电缆", "规格-额定-电压", "尺寸-外径-偏差", "备注"]
    assert data == [["YJV", "10", "20", "ok"], ["KVV", "5", "8", "ok"]]


def test_sheet_without_merges_keeps_a_single_header_row(excel):
    wb = Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append(["1", "2"])

    headers, header_rows, data = _parse(excel, ws)

    assert headers == ["a", "b"]
    assert header_rows == 1
    assert data == [["1", "2"]]


def test_horizontal_merge_does_not_raise_the_header_depth_bound(excel):
    assert excel.Excel()._header_depth_bound(_merged_chinese_sheet([["YJV22", "交联聚乙烯", "铜芯"]])) == 1


def test_vertical_merge_raises_the_header_depth_bound(excel):
    assert excel.Excel()._header_depth_bound(_two_level_merged_sheet()) == 2


def test_row_with_data_values_is_never_a_header_row(excel):
    parser = excel.Excel()

    # A Chinese data row is still "header-like" on content alone, because any
    # non-ASCII cell counts as a header marker. That is precisely why the
    # merged-cell bound is required to protect it.
    chinese_row = excel.Excel._get_rows_limited(_merged_chinese_sheet([["YJV22", "交联聚乙烯", "铜芯"]]))[1]
    assert parser._row_looks_like_header(chinese_row) is True

    # A row carrying numeric values is never a header row.
    numeric_row = excel.Excel._get_rows_limited(_two_level_merged_sheet())[2]
    assert parser._row_looks_like_header(numeric_row) is False
