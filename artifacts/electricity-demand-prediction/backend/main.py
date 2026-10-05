from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.services.data_service import DatasetState, prepare_dataset, preview, profile
from backend.services.model_service import DemandModel
from backend.services.persistence import ResultStore
from backend.services.sample_data import create_sample_csv
from backend.services.spark_service import clean_and_sample_with_spark, spark_availability

logger = logging.getLogger("electricity-analytics")
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = BACKEND_DIR / "models"
DATABASE_PATH = DATA_DIR / "results.sqlite3"
CURRENT_UPLOAD = UPLOAD_DIR / "current_upload.csv"
METADATA_PATH = UPLOAD_DIR / "current_dataset.json"
SAMPLE_CSV = DATA_DIR / "sample_electricity.csv"
PROCESSED_CSV = DATA_DIR / "processed_dataset.csv"
MAX_UPLOAD_BYTES = 150 * 1024 * 1024

app = FastAPI(
    title="Electricity Consumption Analytics & Demand Prediction API",
    description="Data profiling, Spark processing, demand analysis, and scikit-learn forecasting.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CsvDatasetInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    csv_text: str = Field(min_length=1)


class TrainModelInput(BaseModel):
    use_spark: bool = False


class DemandPredictionInput(BaseModel):
    timestamp: datetime
    temperature: float | None = None
    recent_consumption: float | None = None


store = ResultStore(DATABASE_PATH)
state: DatasetState | None = None
model = DemandModel(MODEL_DIR / "best_demand_model.joblib")
last_spark_report: dict[str, Any] | None = None


def _clean_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if not name.lower().endswith(".csv"):
        raise ValueError("Please upload a .csv file.")
    return name[:255]


def _load_frame(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)


def _current_state() -> DatasetState:
    if state is None:
        raise HTTPException(status_code=503, detail="The electricity dataset is still loading.")
    return state


def _load_startup_dataset() -> DatasetState:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CURRENT_UPLOAD.exists():
        frame = _load_frame(CURRENT_UPLOAD)
        metadata = json.loads(METADATA_PATH.read_text()) if METADATA_PATH.exists() else {}
        return prepare_dataset(
            frame,
            filename=metadata.get("filename", CURRENT_UPLOAD.name),
            source="uploaded",
        )
    if not SAMPLE_CSV.exists():
        create_sample_csv(SAMPLE_CSV)
    return prepare_dataset(_load_frame(SAMPLE_CSV), SAMPLE_CSV.name, "sample")


@app.on_event("startup")
def initialize_project() -> None:
    global state
    state = _load_startup_dataset()
    PROCESSED_CSV.parent.mkdir(parents=True, exist_ok=True)
    state.frame[[c for c in state.frame.columns if not c.startswith("_")]].to_csv(PROCESSED_CSV, index=False)
    store.record_dataset(state.filename, len(state.frame), profile(state))
    try:
        # Seed the dashboard with a genuine model run on sample data.
        model.train(state)
        store.record_model_run(model.performance["best_model"], model.performance["metrics"], False)
        logger.info("Initial model trained on %s observations", len(state.frame))
    except Exception:
        logger.exception("Initial model training failed; the user can train from the Models page")


@app.get("/healthz")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/electricity/dataset-info")
def get_dataset_info() -> dict[str, Any]:
    return profile(_current_state())


@app.get("/electricity/dataset-preview")
def get_dataset_preview(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return preview(_current_state(), limit)


@app.post("/electricity/upload")
def upload_dataset(request: CsvDatasetInput) -> dict[str, Any]:
    global state, last_spark_report
    try:
        filename = _clean_filename(request.filename)
        content = request.csv_text.encode("utf-8")
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("The CSV is larger than the 150 MB upload limit.")
        try:
            incoming = pd.read_csv(io.BytesIO(content), low_memory=False)
        except UnicodeDecodeError:
            incoming = pd.read_csv(io.BytesIO(content), encoding="latin-1", low_memory=False)
        candidate = prepare_dataset(incoming, filename, "uploaded")
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_UPLOAD.write_bytes(content)
    METADATA_PATH.write_text(json.dumps({"filename": filename}, indent=2))
    candidate.frame[[c for c in candidate.frame.columns if not c.startswith("_")]].to_csv(PROCESSED_CSV, index=False)
    state = candidate
    last_spark_report = None
    model.performance = {
        "trained": False,
        "best_model": None,
        "metrics": [],
        "actual_vs_predicted": [],
        "feature_names": [],
        "training_rows": 0,
        "units": state.units,
        "spark_used": False,
    }
    model.pipeline = None
    if model.model_path.exists():
        model.model_path.unlink()
    store.record_dataset(filename, len(candidate.frame), profile(candidate))
    return profile(candidate)


@app.get("/electricity/statistics")
def get_statistics() -> dict[str, Any]:
    dataset = _current_state()
    target = dataset.frame["_target"]
    predicted: float | None = None
    if model.performance["trained"]:
        next_time = pd.Timestamp(dataset.frame["_timestamp"].max()) + pd.Timedelta(hours=1)
        try:
            predicted = model.predict(dataset, next_time)
        except Exception:
            logger.exception("Could not create the dashboard next-demand prediction")
    return {
        "total_consumption": float(target.sum()),
        "average_consumption": float(target.mean()),
        "peak_demand": float(target.max()),
        "minimum_demand": float(target.min()),
        "predicted_next_demand": predicted,
        "target_column": dataset.target_column,
        "units": dataset.units,
        "rows_after_cleaning": len(dataset.frame),
        "missing_values_filled": dataset.missing_values_filled,
        "duplicates_removed": dataset.duplicate_rows,
    }


def _apply_filters(
    frame: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
    month: int | None,
    year: int | None,
    hour: int | None,
    day_of_week: int | None,
) -> pd.DataFrame:
    filtered = frame
    timestamps = pd.to_datetime(filtered["_timestamp"])
    if start_date:
        filtered = filtered.loc[timestamps >= pd.Timestamp(start_date)]
        timestamps = pd.to_datetime(filtered["_timestamp"])
    if end_date:
        filtered = filtered.loc[timestamps < pd.Timestamp(end_date) + pd.Timedelta(days=1)]
    timestamps = pd.to_datetime(filtered["_timestamp"])
    if month is not None:
        filtered = filtered.loc[timestamps.dt.month == month]
        timestamps = pd.to_datetime(filtered["_timestamp"])
    if year is not None:
        filtered = filtered.loc[timestamps.dt.year == year]
        timestamps = pd.to_datetime(filtered["_timestamp"])
    if hour is not None:
        filtered = filtered.loc[timestamps.dt.hour == hour]
        timestamps = pd.to_datetime(filtered["_timestamp"])
    if day_of_week is not None:
        filtered = filtered.loc[timestamps.dt.dayofweek == day_of_week]
    return filtered


def _series(grouped: pd.Series, limit: int = 1000) -> list[dict[str, Any]]:
    if len(grouped) > limit:
        step = max(1, len(grouped) // limit)
        grouped = grouped.iloc[::step]
    return [{"label": str(label), "value": float(value)} for label, value in grouped.items()]


@app.get("/electricity/consumption-analysis")
def get_consumption_analysis(
    start_date: str | None = None,
    end_date: str | None = None,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = None,
    hour: int | None = Query(default=None, ge=0, le=23),
    day_of_week: int | None = Query(default=None, ge=0, le=6),
) -> dict[str, Any]:
    dataset = _current_state()
    frame = _apply_filters(dataset.frame, start_date, end_date, month, year, hour, day_of_week)
    if frame.empty:
        return {
            "trend": [], "daily": [], "weekly": [], "monthly": [], "hourly": [],
            "weekday_weekend": [], "seasonal": [], "distribution": [], "correlation": {},
            "units": dataset.units,
        }
    work = frame[["_timestamp", "_target"]].copy()
    work["_timestamp"] = pd.to_datetime(work["_timestamp"])
    work = work.set_index("_timestamp")
    target = work["_target"]
    daily = target.resample("D").sum().dropna()
    weekly = target.resample("W").sum().dropna()
    monthly = target.resample("MS").sum().dropna()
    hourly = target.groupby(work.index.hour).mean()
    day_means = target.groupby(work.index.dayofweek).mean()
    weekdays = [
        {"label": "Weekday" if day < 5 else "Weekend", "value": float(value)}
        for day, value in day_means.items()
    ]
    weekend_map: dict[str, list[float]] = {"Weekday": [], "Weekend": []}
    for weekday, value in zip(work.index.dayofweek, target.to_numpy()):
        weekend_map["Weekend" if weekday >= 5 else "Weekday"].append(float(value))
    weekdays = [
        {"label": label, "value": float(np.mean(values))}
        for label, values in weekend_map.items()
        if values
    ]
    season_values: dict[str, list[float]] = {"Winter": [], "Spring": [], "Summer": [], "Autumn": []}
    for timestamp, value in target.items():
        season = (
            "Winter" if timestamp.month in (12, 1, 2)
            else "Spring" if timestamp.month in (3, 4, 5)
            else "Summer" if timestamp.month in (6, 7, 8)
            else "Autumn"
        )
        season_values[season].append(float(value))
    seasonal = [{"label": name, "value": float(pd.Series(values).mean())} for name, values in season_values.items() if values]
    counts, edges = np.histogram(target.to_numpy(), bins=18)
    distribution = [
        {"label": f"{edges[index]:.1f}–{edges[index + 1]:.1f}", "value": float(count)}
        for index, count in enumerate(counts)
    ]
    numeric = frame.select_dtypes(include="number")
    correlation = {}
    if dataset.target_column in numeric.columns:
        correlation = {
            column: float(value)
            for column, value in numeric.corr(numeric_only=True)[dataset.target_column].dropna().items()
        }
    trend_source = target.resample("D").mean().dropna() if len(target) > 1000 else target
    return {
        "trend": _series(pd.Series(trend_source.to_numpy(), index=trend_source.index)),
        "daily": _series(daily),
        "weekly": _series(weekly),
        "monthly": _series(monthly),
        "hourly": _series(hourly),
        "weekday_weekend": weekdays,
        "seasonal": seasonal,
        "distribution": distribution,
        "correlation": correlation,
        "units": dataset.units,
    }


@app.get("/electricity/peak-demand")
def get_peak_demand() -> dict[str, Any]:
    dataset = _current_state()
    frame = dataset.frame
    peak_index = frame["_target"].idxmax()
    minimum_index = frame["_target"].idxmin()
    top = frame.nlargest(10, "_target").sort_values("_timestamp")
    return {
        "peak_timestamp": pd.Timestamp(frame.loc[peak_index, "_timestamp"]).isoformat(),
        "peak_demand": float(frame.loc[peak_index, "_target"]),
        "minimum_timestamp": pd.Timestamp(frame.loc[minimum_index, "_timestamp"]).isoformat(),
        "minimum_demand": float(frame.loc[minimum_index, "_target"]),
        "top_peaks": [
            {
                "label": pd.Timestamp(row["_timestamp"]).isoformat(),
                "value": float(row["_target"]),
            }
            for _, row in top.iterrows()
        ],
        "units": dataset.units,
    }


@app.get("/electricity/monthly-consumption")
def get_monthly_consumption() -> dict[str, Any]:
    dataset = _current_state()
    frame = dataset.frame.set_index("_timestamp")
    return {
        "series": _series(frame["_target"].resample("MS").sum().dropna()),
        "units": dataset.units,
    }


@app.get("/electricity/hourly-consumption")
def get_hourly_consumption() -> dict[str, Any]:
    dataset = _current_state()
    frame = dataset.frame
    hour_values = pd.to_datetime(frame["_timestamp"]).dt.hour
    return {
        "series": _series(frame["_target"].groupby(hour_values).mean()),
        "units": dataset.units,
    }


@app.post("/electricity/train-model")
def train_model(request: TrainModelInput) -> dict[str, Any]:
    global last_spark_report
    dataset = _current_state()
    training_frame = None
    spark_used = False
    if request.use_spark:
        source_path = CURRENT_UPLOAD if dataset.source == "uploaded" else SAMPLE_CSV
        try:
            training_frame, last_spark_report = clean_and_sample_with_spark(source_path, dataset)
            spark_used = True
        except Exception as exc:
            logger.exception("PySpark training path failed")
            raise HTTPException(
                status_code=503,
                detail=f"PySpark processing failed: {exc}. You can retry with Spark disabled.",
            ) from exc
    try:
        performance = model.train(dataset, training_frame=training_frame, spark_used=spark_used)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.record_model_run(performance["best_model"], performance["metrics"], spark_used)
    return performance


@app.get("/electricity/model-performance")
def get_model_performance() -> dict[str, Any]:
    return model.performance


@app.post("/electricity/predict")
def predict_demand(request: DemandPredictionInput) -> dict[str, Any]:
    dataset = _current_state()
    if not model.performance["trained"]:
        raise HTTPException(status_code=409, detail="Train a demand prediction model before predicting.")
    try:
        predicted = model.predict(
            dataset,
            pd.Timestamp(request.timestamp),
            request.temperature,
            request.recent_consumption,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "timestamp": request.timestamp.isoformat(),
        "predicted_demand": predicted,
        "units": dataset.units,
        "model": model.performance["best_model"],
    }


@app.get("/electricity/spark-info")
def get_spark_info() -> dict[str, Any]:
    info = spark_availability()
    info["details"] += (
        f" Last run: {last_spark_report['cleaned_rows']:,} cleaned rows, "
        f"{last_spark_report['daily_groups']:,} daily groups."
        if last_spark_report
        else " Run model training with the Spark option to execute distributed preprocessing."
    )
    return info
