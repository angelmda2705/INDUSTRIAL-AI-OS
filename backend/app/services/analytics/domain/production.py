"""Production calculations. Row-level helpers only; KPI formulas live in kpis.py."""

from __future__ import annotations

import pandas as pd


def prepare(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = df.copy()
    df["_total_units"] = df["produced_qty"] + df["scrap_qty"].fillna(0)
    return df
