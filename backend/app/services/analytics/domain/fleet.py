"""Fuel efficiency calculations (tank-to-tank method).

For each vehicle, records are ordered by date and odometer. The fuel loaded at
a full fill is assumed to replace the fuel consumed since the previous full
fill; partial fills (``full_tank = no``) are accumulated into the next full
fill. When ``full_tank`` is not provided every load is treated as a full fill
(documented assumption that may add noise to individual intervals).
"""

from __future__ import annotations

import pandas as pd


def prepare(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = df.copy()
    for col in ("_interval_km", "_interval_liters", "_interval_cost", "_kml"):
        df[col] = float("nan")
    df["_odometer_issue"] = False
    df["_cost_per_liter"] = df["total_cost"] / df["liters"]
    ordered = df.sort_values(["vehicle_code", "date", "odometer_km"])
    for _, group in ordered.groupby("vehicle_code", sort=False):
        last_full_odo = None
        acc_liters = 0.0
        acc_cost = 0.0
        cost_known = True
        for idx, row in group.iterrows():
            flag = row["full_tank"]
            full = True if flag is None or (isinstance(flag, float) and flag != flag) else bool(flag)
            if last_full_odo is None:
                if full:
                    last_full_odo = row["odometer_km"]
                continue
            acc_liters += row["liters"]
            if pd.notna(row["total_cost"]):
                acc_cost += row["total_cost"]
            else:
                cost_known = False
            if not full:
                continue
            distance = row["odometer_km"] - last_full_odo
            if distance <= 0:
                df.at[idx, "_odometer_issue"] = True
            else:
                df.at[idx, "_interval_km"] = distance
                df.at[idx, "_interval_liters"] = acc_liters
                df.at[idx, "_interval_cost"] = acc_cost if cost_known else float("nan")
                df.at[idx, "_kml"] = distance / acc_liters
            last_full_odo = row["odometer_km"]
            acc_liters, acc_cost, cost_known = 0.0, 0.0, True
    return df
