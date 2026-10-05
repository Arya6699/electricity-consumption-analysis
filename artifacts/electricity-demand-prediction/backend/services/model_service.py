from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data_service import DatasetState, find_weather_column

MAX_TRAINING_ROWS = 50_000


class DemandModel:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.pipeline: Any | None = None
        self.performance: dict[str, Any] = {
            "trained": False,
            "best_model": None,
            "metrics": [],
            "actual_vs_predicted": [],
            "feature_names": [],
            "training_rows": 0,
            "units": "kWh",
            "spark_used": False,
        }

    @staticmethod
    def _features(frame: pd.DataFrame, state: DatasetState) -> pd.DataFrame:
        timestamps = pd.to_datetime(frame["_timestamp"])
        values = pd.to_numeric(frame["_target"], errors="coerce")
        output = pd.DataFrame(index=frame.index)
        output["hour"] = timestamps.dt.hour
        output["day"] = timestamps.dt.day
        output["day_of_week"] = timestamps.dt.dayofweek
        output["week"] = timestamps.dt.isocalendar().week.astype(int)
        output["month"] = timestamps.dt.month
        output["year"] = timestamps.dt.year
        output["is_weekend"] = (timestamps.dt.dayofweek >= 5).astype(int)
        output["season"] = ((timestamps.dt.month % 12) // 3).astype(int)
        for lag in (1, 24, 168):
            output[f"lag_{lag}"] = values.shift(lag)
        initial = float(values.median())
        for lag in (1, 24, 168):
            output[f"lag_{lag}"] = output[f"lag_{lag}"].fillna(initial)
        weather = find_weather_column(state)
        if weather:
            output[weather] = pd.to_numeric(frame[weather], errors="coerce").fillna(
                pd.to_numeric(frame[weather], errors="coerce").median()
            )
        return output.replace([np.inf, -np.inf], np.nan).fillna(0)

    def train(
        self,
        state: DatasetState,
        training_frame: pd.DataFrame | None = None,
        spark_used: bool = False,
    ) -> dict[str, Any]:
        frame = (training_frame if training_frame is not None else state.frame).copy()
        if len(frame) > MAX_TRAINING_ROWS:
            frame = frame.sample(MAX_TRAINING_ROWS, random_state=31).sort_values("_timestamp")
        frame = frame.sort_values("_timestamp").reset_index(drop=True)
        if len(frame) < 30:
            raise ValueError("At least 30 cleaned observations are required to train and evaluate a model.")
        features = self._features(frame, state)
        target = pd.to_numeric(frame["_target"], errors="coerce").fillna(0)
        split = max(1, int(len(frame) * 0.8))
        if split < 20 or len(frame) - split < 5:
            split = max(1, int(len(frame) * 0.75))
        x_train, x_test = features.iloc[:split], features.iloc[split:]
        y_train, y_test = target.iloc[:split], target.iloc[split:]
        candidates = {
            "Linear Regression": make_pipeline(StandardScaler(), LinearRegression()),
            "Random Forest": RandomForestRegressor(
                n_estimators=80,
                max_depth=18,
                min_samples_leaf=2,
                random_state=31,
                n_jobs=2,
            ),
            "Gradient Boosting": GradientBoostingRegressor(
                n_estimators=90,
                max_depth=2,
                learning_rate=0.06,
                loss="huber",
                random_state=31,
            ),
        }
        metrics: list[dict[str, Any]] = []
        predictions: dict[str, np.ndarray] = {}
        fitted: dict[str, Any] = {}
        for name, estimator in candidates.items():
            estimator.fit(x_train, y_train)
            forecast = np.asarray(estimator.predict(x_test), dtype=float)
            mse = float(mean_squared_error(y_test, forecast))
            metrics.append(
                {
                    "model": name,
                    "mae": float(mean_absolute_error(y_test, forecast)),
                    "mse": mse,
                    "rmse": float(np.sqrt(mse)),
                    "r2": float(r2_score(y_test, forecast)) if y_test.nunique() > 1 else 0.0,
                }
            )
            predictions[name] = forecast
            fitted[name] = estimator
        best_metric = min(metrics, key=lambda row: row["rmse"])
        best_name = best_metric["model"]
        self.pipeline = fitted[best_name]
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self.pipeline, "features": features.columns.tolist(), "best_model": best_name},
            self.model_path,
        )
        best_prediction = predictions[best_name]
        sample_size = min(200, len(y_test))
        start = len(y_test) - sample_size
        timestamps = pd.to_datetime(frame.iloc[split:]["_timestamp"]).iloc[start:]
        samples = [
            {
                "timestamp": timestamp.isoformat(),
                "actual": float(actual),
                "predicted": float(predicted),
            }
            for timestamp, actual, predicted in zip(
                timestamps,
                y_test.iloc[start:].to_numpy(),
                best_prediction[start:],
            )
        ]
        self.performance = {
            "trained": True,
            "best_model": best_name,
            "metrics": metrics,
            "actual_vs_predicted": samples,
            "feature_names": features.columns.tolist(),
            "training_rows": len(frame),
            "units": state.units,
            "spark_used": spark_used,
        }
        return self.performance

    def predict(
        self,
        state: DatasetState,
        timestamp: pd.Timestamp,
        temperature: float | None = None,
        recent_consumption: float | None = None,
    ) -> float:
        if not self.performance["trained"] or self.pipeline is None:
            if self.model_path.exists():
                saved = joblib.load(self.model_path)
                self.pipeline = saved["model"]
            else:
                raise RuntimeError("Train a demand model before requesting predictions.")
        frame = state.frame.sort_values("_timestamp")
        target = pd.to_numeric(frame["_target"], errors="coerce")
        history = pd.to_datetime(frame["_timestamp"])
        last_value = float(target.iloc[-1])
        weather = find_weather_column(state)
        features: dict[str, float] = {
            "hour": timestamp.hour,
            "day": timestamp.day,
            "day_of_week": timestamp.dayofweek,
            "week": int(timestamp.isocalendar().week),
            "month": timestamp.month,
            "year": timestamp.year,
            "is_weekend": int(timestamp.dayofweek >= 5),
            "season": int((timestamp.month % 12) // 3),
            "lag_1": float(recent_consumption if recent_consumption is not None else last_value),
        }
        for lag in (24, 168):
            prior = timestamp - pd.Timedelta(hours=lag)
            earlier = np.flatnonzero(history <= prior)
            features[f"lag_{lag}"] = float(target.iloc[earlier[-1]]) if len(earlier) else last_value
        if weather:
            if temperature is not None and "temp" in weather.lower():
                features[weather] = float(temperature)
            else:
                features[weather] = float(pd.to_numeric(frame[weather], errors="coerce").median())
        order = self.performance.get("feature_names") or list(features)
        row = pd.DataFrame([{key: features.get(key, 0.0) for key in order}], columns=order)
        value = float(self.pipeline.predict(row)[0])
        return max(0.0, value)
