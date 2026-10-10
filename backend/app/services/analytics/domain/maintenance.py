"""Maintenance calculations.

Definitions (also in docs/KPI_CATALOG.md):

* Failure: record with ``event_type = falla``. Corrective work not caused by a
  failure is recorded as ``correctivo`` and does not count for MTBF/MTTR.
* Repair time (h): ``event_end − event_start`` of a failure. Failures without
  ``event_end`` are excluded from MTTR.
* Uptime between failures (h): for consecutive failures of the same asset,
  ``start(failure i+1) − end(failure i)``. Calendar time is used, i.e. the
  asset is assumed to be available for operation between failures; for
  assets that do not run 24/7 MTBF overstates operating time.
"""

from __future__ import annotations

import pandas as pd


def prepare(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    df = df.copy()
    df["_is_failure"] = df["event_type"] == "falla"
    df["_repair_h"] = (df["event_end"] - df["event_start"]).dt.total_seconds() / 3600.0
    df.loc[~df["_is_failure"], "_repair_h"] = float("nan")
    df["_uptime_before_h"] = float("nan")
    df["_interval_issue"] = None
    failures = df[df["_is_failure"]].sort_values(["asset_code", "event_start"])
    for _, group in failures.groupby("asset_code", sort=False):
        prev_end = None
        prev_missing_end = False
        for idx, row in group.iterrows():
            if prev_end is not None:
                uptime = (row["event_start"] - prev_end).total_seconds() / 3600.0
                if uptime >= 0:
                    df.at[idx, "_uptime_before_h"] = uptime
                else:
                    df.at[idx, "_interval_issue"] = "overlap"
            elif prev_missing_end:
                df.at[idx, "_interval_issue"] = "previous_without_end"
            prev_end = row["event_end"] if pd.notna(row["event_end"]) else None
            prev_missing_end = prev_end is None
    costs = df[["parts_cost", "labor_cost", "other_cost"]]
    df["_total_cost"] = costs.sum(axis=1, min_count=1)
    tolerance = int(settings.get("preventive_tolerance_days", 0) or 0)
    prev = (df["event_type"] == "preventivo") & df["scheduled_date"].notna()
    df["_preventive_on_time"] = None
    df.loc[prev, "_preventive_on_time"] = (
        df.loc[prev, "event_start"].dt.normalize() <= df.loc[prev, "scheduled_date"] + pd.Timedelta(days=tolerance)
    )
    return df
