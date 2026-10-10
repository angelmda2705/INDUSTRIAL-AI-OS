"""Conversion of stored records into typed pandas DataFrames."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from app.services.imports.templates import ImportTemplate


def records_frame(rows: Iterable[tuple[int, int, dict]], template: ImportTemplate) -> pd.DataFrame:
    """Build a typed frame from (record_id, source_row, data) tuples."""
    data = [{**payload, "_record_id": rid, "_source_row": src} for rid, src, payload in rows]
    df = pd.DataFrame(data)
    for col in ("_record_id", "_source_row"):
        if col not in df:
            df[col] = pd.Series(dtype="int64")
    if template.generic:
        return df
    for fld in template.fields:
        if fld.name not in df:
            df[fld.name] = None
        if fld.type in ("decimal", "integer"):
            df[fld.name] = pd.to_numeric(df[fld.name], errors="coerce").astype("float64")
        elif fld.type in ("date", "datetime"):
            df[fld.name] = pd.to_datetime(df[fld.name], errors="coerce")
        elif fld.type == "boolean":
            df[fld.name] = df[fld.name].map(lambda v: v if isinstance(v, bool) else None).astype("object")
        else:
            df[fld.name] = df[fld.name].astype("object").where(df[fld.name].notna(), None)
    if template.date_field and len(df):
        df["_month"] = df[template.date_field].dt.to_period("M").dt.start_time.dt.date
    else:
        df["_month"] = None
    return df


def present(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """Rows where all the given columns have values."""
    mask = pd.Series(True, index=df.index)
    for c in cols:
        mask &= df[c].notna()
    return df[mask]
