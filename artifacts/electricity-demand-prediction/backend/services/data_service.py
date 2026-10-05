from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TIME_HINTS = ("timestamp", "datetime", "date_time", "date", "time")
TARGET_HINTS = ("consumption", "electricity", "energy", "demand", "load", "power", "usage", "kwh")
WEATHER_HINTS = ("temperature", "temp", "humidity", "weather", "pressure")


@dataclass
class DatasetState:
    frame: pd.DataFrame
    filename: str
    source: str
    raw_rows: int
    duplicate_rows: int
    missing_values_filled: int
    initial_missing_values: dict[str, int]
    target_column: str
    datetime_column: str
    units: str


def _detect_datetime(frame: pd.DataFrame) -> tuple[str, pd.Series]:
    columns = list(frame.columns)
    ranked = sorted(
        columns,
        key=lambda name: (not any(hint in name.lower() for hint in TIME_HINTS), columns.index(name)),
    )
    best_name, best_series, best_ratio = "", None, 0.0
    for name in ranked:
        raw = frame[name]
        parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
        ratio = float(parsed.notna().mean()) if len(frame) else 0.0
        if ratio > best_ratio:
            best_name, best_series, best_ratio = name, parsed, ratio
    if best_series is None or best_ratio < 0.7:
        date_col = next((c for c in columns if "date" in c.lower()), None)
        hour_col = next((c for c in columns if c.lower() in {"hour", "hours"}), None)
        if date_col and hour_col:
            combined = frame[date_col].astype(str) + " " + frame[hour_col].astype(str) + ":00:00"
            parsed = pd.to_datetime(combined, errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.7:
                return f"{date_col} + {hour_col}", parsed
        raise ValueError("Could not identify a date/time column. Include a timestamp, datetime, or date column.")
    return best_name, best_series


def _detect_target(frame: pd.DataFrame, timestamp_name: str) -> str:
    numeric: list[str] = []
    for column in frame.columns:
        if column == timestamp_name or column.lower() in {"hour", "day", "month", "year", "id", "index"}:
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().mean() >= 0.5 and converted.nunique(dropna=True) >= 1:
            numeric.append(column)
    if not numeric:
        raise ValueError("No numeric electricity consumption column was found.")

    def score(name: str) -> tuple[int, float]:
        lowered = name.lower()
        hints = sum(1 for hint in TARGET_HINTS if hint in lowered)
        # Prefer named electricity measurements; otherwise choose the most variable numeric signal.
        variance = float(pd.to_numeric(frame[name], errors="coerce").var())
        return hints, variance if not re.search(r"(^|_)(id|index|serial)($|_)", lowered) else -1

    return max(numeric, key=score)


def infer_units(column: str) -> str:
    lower = column.lower()
    if "mwh" in lower:
        return "MWh"
    if re.search(r"(^|[^m])mw([^h]|$)", lower):
        return "MW"
    if "kw" in lower and "kwh" not in lower:
        return "kW"
    return "kWh"


def prepare_dataset(
    frame: pd.DataFrame,
    filename: str,
    source: str,
    datetime_name: str | None = None,
) -> DatasetState:
    """Normalize timestamps, fill missing values, remove duplicates and clip IQR outliers."""
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("The CSV must contain at least two columns and one data row.")
    raw_rows = len(frame)
    initial_missing_values = {str(column): int(frame[column].isna().sum()) for column in frame.columns}
    duplicate_rows = int(frame.duplicated().sum())
    cleaned = frame.drop_duplicates().copy()
    detected_datetime, parsed_times = _detect_datetime(cleaned) if datetime_name is None else (
        datetime_name,
        pd.to_datetime(cleaned[datetime_name], errors="coerce", format="mixed"),
    )
    if " + " in detected_datetime:
        date_name, hour_name = detected_datetime.split(" + ")
        timestamp_values = pd.to_datetime(
            cleaned[date_name].astype(str) + " " + cleaned[hour_name].astype(str) + ":00:00",
            errors="coerce",
            format="mixed",
        )
        source_datetime = date_name
    else:
        timestamp_values = parsed_times
        source_datetime = detected_datetime
    target = _detect_target(cleaned, source_datetime)
    cleaned["_timestamp"] = timestamp_values
    cleaned["_target"] = pd.to_numeric(cleaned[target], errors="coerce")
    cleaned = cleaned.dropna(subset=["_timestamp"])
    if cleaned.empty or cleaned["_target"].notna().sum() < 5:
        raise ValueError("The dataset needs at least five rows with valid timestamps and numeric consumption.")

    before_fills = int(cleaned.isna().sum().sum())
    for column in cleaned.select_dtypes(include=[np.number]).columns:
        median = cleaned[column].median()
        cleaned[column] = cleaned[column].fillna(median if pd.notna(median) else 0)
    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        mode = cleaned[column].mode(dropna=True)
        cleaned[column] = cleaned[column].fillna(mode.iloc[0] if not mode.empty else "Unknown")
    cleaned["_target"] = cleaned["_target"].interpolate(limit_direction="both")
    # IQR capping keeps isolated sensor spikes from dominating model fitting while retaining rows.
    q1, q3 = cleaned["_target"].quantile([0.25, 0.75])
    iqr = q3 - q1
    if pd.notna(iqr) and iqr > 0:
        cleaned["_target"] = cleaned["_target"].clip(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    cleaned[target] = cleaned["_target"]
    cleaned = cleaned.sort_values("_timestamp").reset_index(drop=True)
    filled = max(0, before_fills - int(cleaned.isna().sum().sum()))
    return DatasetState(
        frame=cleaned,
        filename=filename,
        source=source,
        raw_rows=raw_rows,
        duplicate_rows=duplicate_rows,
        missing_values_filled=filled,
        initial_missing_values=initial_missing_values,
        target_column=target,
        datetime_column=source_datetime,
        units=infer_units(target),
    )


def profile(state: DatasetState) -> dict[str, Any]:
    frame = state.frame
    original_columns = [c for c in frame.columns if not c.startswith("_")]
    numeric_target = frame["_target"]
    numeric_summary = numeric_target.describe()
    summary = {
        "mean": float(numeric_summary["mean"]),
        "std": float(numeric_summary["std"]),
        "min": float(numeric_summary["min"]),
        "25%": float(numeric_summary["25%"]),
        "50%": float(numeric_summary["50%"]),
        "75%": float(numeric_summary["75%"]),
        "max": float(numeric_summary["max"]),
    }
    missing_values = {
        column: state.initial_missing_values.get(column, int(frame[column].isna().sum()))
        for column in original_columns
    }
    return {
        "filename": state.filename,
        "source": state.source,
        "rows": len(frame),
        "column_count": len(original_columns),
        "columns": original_columns,
        "data_types": {column: str(frame[column].dtype) for column in original_columns},
        "missing_values": missing_values,
        "duplicate_rows": state.duplicate_rows,
        "target_column": state.target_column,
        "datetime_column": state.datetime_column,
        "units": state.units,
        "summary": summary,
    }


def preview(state: DatasetState, limit: int = 20) -> dict[str, Any]:
    visible = [c for c in state.frame.columns if not c.startswith("_")]
    rows: list[dict[str, str | None]] = []
    for row in state.frame[visible].head(max(1, min(limit, 100))).to_dict(orient="records"):
        rows.append(
            {
                key: None if pd.isna(value) else (value.isoformat() if hasattr(value, "isoformat") else str(value))
                for key, value in row.items()
            }
        )
    return {"columns": visible, "rows": rows, "total_rows": len(state.frame)}


def find_weather_column(state: DatasetState) -> str | None:
    for column in state.frame.columns:
        if column.startswith("_"):
            continue
        if any(hint in column.lower() for hint in WEATHER_HINTS) and pd.api.types.is_numeric_dtype(state.frame[column]):
            return column
    return None
