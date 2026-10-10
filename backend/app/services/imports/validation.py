"""Type conversion and validation of imported rows.

Conversion rules (documented for users in docs/USER_MANUAL.md):

* Empty cells and the markers ``NA``, ``N/A``, ``null``, ``-`` are missing values.
* Decimals accept thousands separators according to ``decimal_separator``
  ("." → ``1,234.5``; "," → ``1.234,5``) and a leading ``$``.
* Dates accept ISO (``2024-03-31``), Excel date cells, Excel serial numbers and
  ``dd/mm/yyyy`` or ``mm/dd/yyyy`` depending on ``date_format``.
* Datetimes are stored without time-zone offset and interpreted in the
  organization's configured time zone.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from app.services.imports.parsing import ParsedTable, jsonable, normalize_header
from app.services.imports.templates import ImportTemplate, TemplateField

MISSING_MARKERS = {"", "na", "n/a", "null", "none", "-", "--", "nan", "#n/a"}
TRUE_VALUES = {"si", "sí", "s", "yes", "y", "true", "1", "verdadero", "x", "lleno"}
FALSE_VALUES = {"no", "n", "false", "0", "falso"}
MAX_REPORTED_ERRORS = 500
EXCEL_EPOCH = datetime(1899, 12, 30)


class ConversionError(ValueError):
    pass


@dataclass
class ParseOptions:
    decimal_separator: str = "."  # "." or ","
    date_format: str = "dayfirst"  # "dayfirst" | "monthfirst"


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip().lower() in MISSING_MARKERS


def _strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def to_decimal(value: Any, opts: ParseOptions) -> float:
    if isinstance(value, bool):
        raise ConversionError("Se esperaba un número.")
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = str(value).strip().replace(" ", "").replace(" ", "")
        text = re.sub(r"^\$|^MXN|^USD|^€", "", text, flags=re.IGNORECASE)
        negative = text.startswith("(") and text.endswith(")")
        if negative:
            text = text[1:-1]
        if opts.decimal_separator == ",":
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
        if not re.fullmatch(r"[-+]?\d+(\.\d+)?|[-+]?\.\d+", text):
            raise ConversionError("Se esperaba un número (ej. 1234.50).")
        result = float(text)
        if negative:
            result = -result
    if not math.isfinite(result):
        raise ConversionError("Número no válido.")
    return result


_ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?(?:Z|[+-]\d{2}:?\d{2})?$")
_DMY_RE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$")


def to_datetime(value: Any, opts: ParseOptions) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 <= value <= 80000:  # Excel serial date (1954-2119)
            return (EXCEL_EPOCH + timedelta(days=float(value))).replace(microsecond=0)
        raise ConversionError("Se esperaba una fecha.")
    text = str(value).strip()
    try:
        m = _ISO_RE.match(text)
        if m:
            y, mo, d, hh, mm, ss = m.groups()
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
        m = _DMY_RE.match(text)
        if m:
            a, b, y, hh, mm, ss = m.groups()
            day, month = (int(a), int(b)) if opts.date_format == "dayfirst" else (int(b), int(a))
            year = int(y) + (2000 if len(y) == 2 else 0)
            return datetime(year, month, day, int(hh or 0), int(mm or 0), int(ss or 0))
    except ValueError as exc:
        raise ConversionError("Fecha inexistente (revisa día y mes).") from exc
    fmt = "dd/mm/aaaa" if opts.date_format == "dayfirst" else "mm/dd/aaaa"
    raise ConversionError(f"Fecha no reconocida. Usa aaaa-mm-dd o {fmt}.")


def convert(fld: TemplateField, value: Any, opts: ParseOptions) -> Any:
    if fld.type == "string":
        if isinstance(value, float) and value.is_integer():
            text = str(int(value))
        elif isinstance(value, (datetime, date)):
            text = value.isoformat()
        else:
            text = str(value).strip()
        if len(text) > fld.max_length:
            raise ConversionError(f"Texto demasiado largo (máximo {fld.max_length} caracteres).")
        return text
    if fld.type in ("decimal", "integer"):
        number = to_decimal(value, opts)
        if fld.type == "integer":
            if not float(number).is_integer():
                raise ConversionError("Se esperaba un número entero.")
            number = int(number)
        if fld.min_value is not None and number < fld.min_value:
            raise ConversionError(f"Debe ser mayor o igual a {fld.min_value:g}.")
        if fld.max_value is not None and number > fld.max_value:
            raise ConversionError(f"Debe ser menor o igual a {fld.max_value:g}.")
        return number
    if fld.type == "date":
        return to_datetime(value, opts).date().isoformat()
    if fld.type == "datetime":
        return to_datetime(value, opts).isoformat(timespec="seconds")
    if fld.type == "boolean":
        if isinstance(value, bool):
            return value
        text = _strip_accents(str(value).strip().lower())
        if text in TRUE_VALUES:
            return True
        if text in FALSE_VALUES:
            return False
        raise ConversionError("Se esperaba sí/no.")
    if fld.type == "enum":
        text = _strip_accents(str(value).strip().lower())
        if text in fld.choices:
            return text
        aliases = dict(fld.choice_aliases)
        if text in aliases:
            return aliases[text]
        raise ConversionError(f"Valor no permitido. Opciones: {', '.join(fld.choices)}.")
    raise ConversionError("Tipo de campo desconocido.")


def _generic_value(value: Any) -> Any:
    if is_missing(value):
        return None
    if isinstance(value, float) and value.is_integer() and abs(value) < 2**53:
        return int(value)
    return jsonable(value)


def fingerprint(values: dict, keys: list[str]) -> str:
    payload = json.dumps([values.get(k) for k in keys], ensure_ascii=False, default=str, sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def suggest_mapping(template: ImportTemplate, columns: list[str]) -> dict[str, str]:
    normalized = {normalize_header(c): c for c in columns}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for fld in template.fields:
        candidates = [fld.name.replace("_", " "), fld.label, *fld.synonyms]
        for cand in candidates:
            col = normalized.get(normalize_header(cand))
            if col and col not in used:
                mapping[fld.name] = col
                used.add(col)
                break
    return mapping


def check_mapping(template: ImportTemplate, mapping: dict[str, str], columns: list[str]) -> list[dict]:
    """Return mapping problems (empty list when valid)."""
    problems = []
    if template.generic:
        return problems
    field_names = {f.name for f in template.fields}
    for target, source in mapping.items():
        if target not in field_names:
            problems.append({"field": target, "message": "Campo destino desconocido."})
        elif source not in columns:
            problems.append({"field": target, "message": f"La columna '{source}' no existe en el archivo."})
    sources = [s for s in mapping.values() if s]
    for dup in {s for s in sources if sources.count(s) > 1}:
        problems.append({"field": dup, "message": "La misma columna está asignada a varios campos."})
    for fld in template.fields:
        if fld.required and not mapping.get(fld.name):
            problems.append({"field": fld.name, "message": f"El campo obligatorio '{fld.label}' no tiene columna asignada."})
    return problems


@dataclass
class ValidRow:
    source_row: int
    data: dict
    fingerprint: str


@dataclass
class ValidationResult:
    valid: list[ValidRow] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    error_rows: int = 0
    duplicate_in_file: list[dict] = field(default_factory=list)
    duplicate_existing: list[int] = field(default_factory=list)
    missing_by_field: dict[str, int] = field(default_factory=dict)
    duplicate_basis: list[str] = field(default_factory=list)

    def summary(self, total_rows: int, unmapped_columns: list[str]) -> dict:
        dup_rows = {d["row"] for d in self.duplicate_in_file} | set(self.duplicate_existing)
        return {
            "total_rows": total_rows,
            "valid_rows": len(self.valid),
            "invalid_rows": self.error_rows,
            "duplicate_rows": len(dup_rows),
            "duplicates_in_file": self.duplicate_in_file[:MAX_REPORTED_ERRORS],
            "duplicates_existing_rows": self.duplicate_existing[:MAX_REPORTED_ERRORS],
            "importable_rows_without_duplicates": len([v for v in self.valid if v.source_row not in dup_rows]),
            "errors": self.errors[:MAX_REPORTED_ERRORS],
            "errors_truncated": len(self.errors) > MAX_REPORTED_ERRORS,
            "missing_by_field": self.missing_by_field,
            "duplicate_basis": self.duplicate_basis,
            "unmapped_columns": unmapped_columns,
        }


def validate_rows(
    template: ImportTemplate,
    mapping: dict[str, str],
    table: ParsedTable,
    opts: ParseOptions,
    existing_fingerprints: set[str] | None = None,
) -> ValidationResult:
    result = ValidationResult()
    existing_fingerprints = existing_fingerprints or set()
    col_index = {c: i for i, c in enumerate(table.columns)}
    seen: dict[str, int] = {}

    if template.generic:
        keys = list(table.columns)
        result.duplicate_basis = ["renglón completo"]
        for source_row, values in table.rows:
            data = {c: _generic_value(values[i]) for c, i in col_index.items()}
            for c, v in data.items():
                if v is None:
                    result.missing_by_field[c] = result.missing_by_field.get(c, 0) + 1
            fp = fingerprint(data, keys)
            _register(result, ValidRow(source_row, data, fp), seen, existing_fingerprints)
        return result

    mapped_fields = [f for f in template.fields if mapping.get(f.name)]
    key_fields = [k for k in template.key_fields if mapping.get(k)]
    keys = key_fields or [f.name for f in mapped_fields]
    result.duplicate_basis = [template.field(k).label for k in keys]
    for f in mapped_fields:
        result.missing_by_field[f.name] = 0

    for source_row, values in table.rows:
        data: dict[str, Any] = {}
        row_errors: list[dict] = []
        for fld in mapped_fields:
            column = mapping[fld.name]
            raw = values[col_index[column]]
            if is_missing(raw):
                result.missing_by_field[fld.name] += 1
                data[fld.name] = None
                if fld.required:
                    row_errors.append(_err(source_row, fld, column, raw, "Valor obligatorio vacío."))
                continue
            try:
                data[fld.name] = convert(fld, raw, opts)
            except ConversionError as exc:
                data[fld.name] = None
                row_errors.append(_err(source_row, fld, column, raw, str(exc)))
        for a, op, b, message in template.cross_rules:
            va, vb = data.get(a), data.get(b)
            if va is not None and vb is not None and not (va <= vb if op == "<=" else va >= vb):
                row_errors.append(_err(source_row, template.field(b), mapping.get(b), vb, message))
        if row_errors:
            result.error_rows += 1
            result.errors.extend(row_errors)
            continue
        _register(result, ValidRow(source_row, data, fingerprint(data, keys)), seen, existing_fingerprints)
    return result


def _register(result: ValidationResult, row: ValidRow, seen: dict[str, int], existing: set[str]) -> None:
    if row.fingerprint in existing:
        result.duplicate_existing.append(row.source_row)
    elif row.fingerprint in seen:
        result.duplicate_in_file.append({"row": row.source_row, "duplicate_of_row": seen[row.fingerprint]})
    else:
        seen[row.fingerprint] = row.source_row
    result.valid.append(row)


def _err(row: int, fld: TemplateField, column: str | None, value: Any, message: str) -> dict:
    shown = jsonable(value)
    if isinstance(shown, str) and len(shown) > 80:
        shown = shown[:80] + "…"
    return {"row": row, "field": fld.name, "field_label": fld.label, "column": column, "value": shown, "message": message}
