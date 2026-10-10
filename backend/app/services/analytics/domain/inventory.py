"""Inventory item metrics: value, ABC class, safety stock and reorder point.

* Annual consumption value = avg_daily_demand × 365 × unit_cost.
* ABC: items sorted by annual consumption value; cumulative share ≤ A
  threshold → A, ≤ B threshold → B, rest → C (thresholds configurable,
  default 80 % / 95 %). Items without demand or cost are "Sin clasificar".
* Safety stock = z × σ_d × √L (demand variability only; lead-time variability
  is not modelled). z defaults to 1.645 (≈95 % cycle service level under a
  normal demand assumption). Without σ_d the safety stock is not computed.
* Reorder point = d × L + safety stock (safety stock = 0 when not computable,
  flagged in ``_rop_basis``).
* Coverage (days) = on_hand / d.
* Obsolescence reference date = most recent ``last_movement_date`` in the
  dataset (keeps results reproducible instead of depending on "today").
"""

from __future__ import annotations

import math

import pandas as pd


def prepare(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = df.copy()
    z = float(settings.get("inventory_service_level_z", 1.645))
    a_thr, b_thr = settings.get("inventory_abc_thresholds", [0.8, 0.95])
    obsolete_days = int(settings.get("inventory_obsolete_days", 180))

    df["_value"] = df["on_hand_qty"].clip(lower=0) * df["unit_cost"]
    df["_annual_value"] = df["avg_daily_demand"] * 365.0 * df["unit_cost"]
    df["_abc"] = "Sin clasificar"
    classified = df[df["_annual_value"].notna() & (df["_annual_value"] > 0)].sort_values("_annual_value", ascending=False)
    total = classified["_annual_value"].sum()
    if total > 0:
        cumulative = classified["_annual_value"].cumsum() / total
        # An item belongs to A while the cumulative share *before* it is below the threshold.
        prev_share = cumulative - classified["_annual_value"] / total
        df.loc[classified.index, "_abc"] = [
            "A" if p < a_thr else ("B" if p < b_thr else "C") for p in prev_share
        ]

    has_dl = df["avg_daily_demand"].notna() & df["lead_time_days"].notna()
    df["_safety_stock"] = float("nan")
    with_sigma = has_dl & df["demand_std_daily"].notna()
    df.loc[with_sigma, "_safety_stock"] = (
        z * df.loc[with_sigma, "demand_std_daily"] * df.loc[with_sigma, "lead_time_days"].map(math.sqrt)
    )
    df["_rop"] = float("nan")
    df.loc[has_dl, "_rop"] = df.loc[has_dl, "avg_daily_demand"] * df.loc[has_dl, "lead_time_days"] + df.loc[
        has_dl, "_safety_stock"
    ].fillna(0.0)
    df["_rop_basis"] = None
    df.loc[with_sigma, "_rop_basis"] = "d·L + z·σ·√L"
    df.loc[has_dl & ~with_sigma, "_rop_basis"] = "d·L (sin stock de seguridad: falta σ)"

    df["_coverage_days"] = float("nan")
    pos_d = df["avg_daily_demand"] > 0
    df.loc[pos_d, "_coverage_days"] = df.loc[pos_d, "on_hand_qty"] / df.loc[pos_d, "avg_daily_demand"]

    df["_below_rop"] = has_dl & pos_d & (df["on_hand_qty"] <= df["_rop"])
    df["_stockout"] = pos_d & (df["on_hand_qty"] <= 0)
    df["_negative"] = df["on_hand_qty"] < 0
    df["_excess_qty"] = (df["on_hand_qty"] - df["max_qty"]).where(df["max_qty"].notna() & (df["on_hand_qty"] > df["max_qty"]))
    df["_excess_value"] = df["_excess_qty"] * df["unit_cost"]

    df["_days_without_movement"] = float("nan")
    df["_obsolete_candidate"] = False
    if df["last_movement_date"].notna().any():
        ref = df["last_movement_date"].max()
        df["_days_without_movement"] = (ref - df["last_movement_date"]).dt.days
        df["_obsolete_candidate"] = (df["_days_without_movement"] > obsolete_days) & (df["on_hand_qty"] > 0)
        df.attrs["obsolescence_reference_date"] = ref.date().isoformat()

    # Suggested replenishment (proposal only; nothing is ordered automatically).
    suggested = pd.Series(float("nan"), index=df.index)
    with_max = df["_below_rop"] & df["max_qty"].notna()
    suggested[with_max] = df.loc[with_max, "max_qty"] - df.loc[with_max, "on_hand_qty"]
    no_max = df["_below_rop"] & df["max_qty"].isna()
    suggested[no_max] = (
        df.loc[no_max, "_rop"] + df.loc[no_max, "avg_daily_demand"] * df.loc[no_max, "lead_time_days"] - df.loc[no_max, "on_hand_qty"]
    )
    df["_suggested_order_qty"] = suggested.clip(lower=0)
    return df
