import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from app.core.errors import ValidationFailed
from app.services.imports.parsing import ParsedTable, detect_file_type, read_csv, read_xlsx
from app.services.imports.templates import FUEL, MAINTENANCE, PRODUCTION
from app.services.imports.validation import (
    ConversionError,
    ParseOptions,
    check_mapping,
    convert,
    suggest_mapping,
    to_datetime,
    to_decimal,
    validate_rows,
)

DOT, COMMA = ParseOptions("."), ParseOptions(",")


def test_csv_semicolon_latin1_duplicate_headers_and_blank_rows():
    data = "Fecha;Línea;Línea;\n\n01/02/2024;A;B;\n;;;\n02/02/2024;C;D;\n".encode("cp1252")
    t = read_csv(data, max_rows=100)
    assert t.delimiter == ";" and t.encoding == "cp1252"
    assert t.columns == ["Fecha", "Línea", "Línea_2", "columna_4"]
    assert [r[0] for r in t.rows] == [3, 5]  # source line numbers survive blank rows


def test_csv_row_limit():
    data = ("a,b\n" + "1,2\n" * 11).encode()
    with pytest.raises(ValidationFailed) as exc:
        read_csv(data, max_rows=10)
    assert exc.value.code == "too_many_rows"


def test_binary_file_rejected_as_csv():
    with pytest.raises(ValidationFailed):
        read_csv(b"\x00\x01\x02binary", max_rows=10)


def _xlsx(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    for r in rows:
        ws.append(r)
    wb.create_sheet("Otra").append(["x"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_reads_native_types_and_sheets():
    data = _xlsx([[None], ["Fecha", "Cantidad"], [datetime(2024, 3, 1), 10.5], [None, None], [datetime(2024, 3, 2), 3]])
    t = read_xlsx(data, max_rows=100, max_uncompressed=10**8)
    assert t.sheet_names == ["Datos", "Otra"]
    assert t.columns == ["Fecha", "Cantidad"]
    assert t.rows[0] == (3, [datetime(2024, 3, 1), 10.5])
    assert len(t.rows) == 2
    t2 = read_xlsx(data, max_rows=100, max_uncompressed=10**8, sheet="Otra")
    assert t2.columns == ["x"]
    with pytest.raises(ValidationFailed):
        read_xlsx(data, max_rows=100, max_uncompressed=10**8, sheet="No existe")


def test_xlsx_decompression_limit_and_corrupt_file():
    data = _xlsx([["a"], [1]])
    with pytest.raises(ValidationFailed) as exc:
        read_xlsx(data, max_rows=100, max_uncompressed=100)
    assert exc.value.code == "file_too_large"
    with pytest.raises(ValidationFailed):
        read_xlsx(b"PK\x03\x04garbage", max_rows=10, max_uncompressed=10**8)


def test_file_type_detection():
    assert detect_file_type("datos.CSV", b"a,b") == "csv"
    assert detect_file_type("libro.xlsx", b"PK\x03\x04...") == "xlsx"
    for name, data in (("libro.xlsx", b"not zip"), ("viejo.xls", b""), ("macro.xlsm", b"PK"), ("x.exe", b"MZ")):
        with pytest.raises(ValidationFailed):
            detect_file_type(name, data)


@pytest.mark.parametrize("raw,opts,expected", [
    ("1,234.50", DOT, 1234.5), ("1.234,50", COMMA, 1234.5), ("$ 99", DOT, 99.0), ("(12.5)", DOT, -12.5),
    (7, DOT, 7.0), ("-3", DOT, -3.0), (".5", DOT, 0.5),
])
def test_decimal_conversion(raw, opts, expected):
    assert to_decimal(raw, opts) == expected


@pytest.mark.parametrize("raw", ["12%", "abc", "1.2.3", True, "nan"])
def test_decimal_rejections(raw):
    with pytest.raises(ConversionError):
        to_decimal(raw, DOT)


def test_dates_dayfirst_monthfirst_iso_and_excel_serial():
    assert to_datetime("03/04/2024", ParseOptions(date_format="dayfirst")) == datetime(2024, 4, 3)
    assert to_datetime("03/04/2024", ParseOptions(date_format="monthfirst")) == datetime(2024, 3, 4)
    assert to_datetime("2024-04-03T10:15", DOT) == datetime(2024, 4, 3, 10, 15)
    assert to_datetime("03-04-24 7:05", DOT) == datetime(2024, 4, 3, 7, 5)
    assert to_datetime(45383, DOT) == datetime(2024, 4, 1)
    with pytest.raises(ConversionError):
        to_datetime("31/02/2024", DOT)
    with pytest.raises(ConversionError):
        to_datetime("ayer", DOT)


def test_field_conversion_rules():
    assert convert(MAINTENANCE.field("event_type"), "Falla", DOT) == "falla"
    assert convert(MAINTENANCE.field("event_type"), "Preventive", DOT) == "preventivo"
    with pytest.raises(ConversionError):
        convert(MAINTENANCE.field("event_type"), "otro", DOT)
    assert convert(FUEL.field("full_tank"), "Sí", DOT) is True
    assert convert(FUEL.field("full_tank"), "no", DOT) is False
    assert convert(FUEL.field("vehicle_code"), 1001.0, DOT) == "1001"
    with pytest.raises(ConversionError):
        convert(FUEL.field("liters"), "0", DOT)  # min 0.001
    with pytest.raises(ConversionError):
        convert(PRODUCTION.field("produced_qty"), "-1", DOT)


def test_suggest_and_check_mapping():
    cols = ["FECHA", "Línea", "Piezas Buenas", "Scrap", "Otra"]
    mapping = suggest_mapping(PRODUCTION, cols)
    assert mapping == {"date": "FECHA", "work_center": "Línea", "produced_qty": "Piezas Buenas", "scrap_qty": "Scrap"}
    assert check_mapping(PRODUCTION, mapping, cols) == []
    problems = check_mapping(PRODUCTION, {"date": "FECHA", "work_center": "FECHA", "bogus": "x"}, cols)
    messages = " ".join(p["message"] for p in problems)
    assert "desconocido" in messages and "varios campos" in messages and "obligatorio" in messages


def test_validate_rows_errors_duplicates_and_cross_rules():
    table = ParsedTable(
        columns=["Equipo", "Tipo", "Inicio", "Fin"],
        rows=[
            (2, ["P1", "falla", "2024-01-01 08:00", "2024-01-01 10:00"]),
            (3, ["P1", "falla", "2024-01-01 08:00", "2024-01-01 10:00"]),  # duplicate key
            (4, ["P1", "falla", "2024-01-05 08:00", "2024-01-04 10:00"]),  # end before start
            (5, ["", "falla", "2024-01-06 08:00", ""]),  # missing required
            (6, ["P2", "falla", "2024-01-06 08:00", "NA"]),  # NA = missing optional
        ],
    )
    mapping = {"asset_code": "Equipo", "event_type": "Tipo", "event_start": "Inicio", "event_end": "Fin"}
    result = validate_rows(MAINTENANCE, mapping, table, DOT, existing_fingerprints=set())
    assert result.error_rows == 2
    assert {e["row"] for e in result.errors} == {4, 5}
    assert result.duplicate_in_file == [{"row": 3, "duplicate_of_row": 2}]
    assert result.missing_by_field["event_end"] == 2
    existing = {result.valid[0].fingerprint}
    again = validate_rows(MAINTENANCE, mapping, table, DOT, existing_fingerprints=existing)
    assert 2 in again.duplicate_existing and 3 in again.duplicate_existing
