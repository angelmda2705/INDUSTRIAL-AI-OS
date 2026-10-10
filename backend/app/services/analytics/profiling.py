"""Data-quality profile of a dataset."""

from __future__ import annotations

import pandas as pd

from app.services.analytics.stats import round_or_none
from app.services.imports.templates import ImportTemplate


def _field_specs(template: ImportTemplate, df: pd.DataFrame) -> list[tuple[str, str, str]]:
    if template.generic:
        cols = [c for c in df.columns if not c.startswith("_")]
        specs = []
        for c in cols:
            numeric = pd.to_numeric(df[c], errors="coerce")
            kind = "decimal" if len(df) and numeric.notna().sum() >= 0.9 * df[c].notna().sum() and df[c].notna().any() else "string"
            specs.append((c, c, kind))
        return specs
    return [(f.name, f.label, f.type) for f in template.fields]


def profile(df: pd.DataFrame, template: ImportTemplate, mapped_fields: set[str] | None = None) -> dict:
    n = len(df)
    fields = []
    total_cells = 0
    missing_cells = 0
    for name, label, kind in _field_specs(template, df):
        if mapped_fields is not None and not template.generic and name not in mapped_fields:
            continue
        series = df[name] if name in df else pd.Series([None] * n)
        missing = int(series.isna().sum())
        total_cells += n
        missing_cells += missing
        info: dict = {
            "field": name,
            "label": label,
            "type": kind,
            "missing": missing,
            "missing_pct": round_or_none(missing / n * 100, 2) if n else None,
            "distinct": int(series.nunique(dropna=True)),
        }
        non_null = series.dropna()
        if kind in ("decimal", "integer") and len(non_null):
            values = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(values):
                q1, q3 = values.quantile(0.25), values.quantile(0.75)
                iqr = q3 - q1
                outliers = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
                info.update(
                    min=round_or_none(values.min()), max=round_or_none(values.max()), mean=round_or_none(values.mean()),
                    median=round_or_none(values.median()), std=round_or_none(values.std()) if len(values) > 1 else None,
                    negatives=int((values < 0).sum()), iqr_outliers=outliers,
                )
        elif kind in ("date", "datetime") and len(non_null):
            info.update(min=str(non_null.min()), max=str(non_null.max()))
        elif len(non_null):
            top = non_null.astype(str).value_counts().head(5)
            info["top_values"] = [{"value": k[:80], "count": int(v)} for k, v in top.items()]
        fields.append(info)
    date_range = None
    if template.date_field and n and df[template.date_field].notna().any():
        date_range = {"from": df[template.date_field].min().date().isoformat(), "to": df[template.date_field].max().date().isoformat()}
    return {
        "row_count": n,
        "completeness_pct": round_or_none((1 - missing_cells / total_cells) * 100, 2) if total_cells else None,
        "completeness_definition": "Celdas con valor ÷ celdas de los campos mapeados × 100",
        "date_range": date_range,
        "fields": fields,
    }
