from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def create_sample_csv(path: Path) -> Path:
    """Create one year of hourly, deterministic sample readings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.date_range("2024-01-01", periods=24 * 366, freq="h")
    hour = timestamps.hour.to_numpy()
    day = timestamps.dayofyear.to_numpy()
    weekend = (timestamps.dayofweek >= 5).astype(int)
    temperature = (
        17
        + 10 * np.sin(2 * np.pi * (day - 105) / 366)
        + 4 * np.sin(2 * np.pi * (hour - 8) / 24)
    )
    morning = 18 * np.exp(-0.5 * ((hour - 8) / 2.1) ** 2)
    evening = 31 * np.exp(-0.5 * ((hour - 19) / 3.0) ** 2)
    daily = 12 * np.sin(2 * np.pi * (hour - 13) / 24)
    seasonal = 26 + 0.85 * np.maximum(temperature - 24, 0)
    rng = np.random.default_rng(27)
    consumption = (
        seasonal
        + morning
        + evening
        + daily
        - 5 * weekend
        + rng.normal(0, 3.8, len(timestamps))
    ).clip(min=5)

    pd.DataFrame(
        {
            "timestamp": timestamps,
            "consumption_kwh": consumption.round(3),
            "temperature_c": temperature.round(2),
        }
    ).to_csv(path, index=False)
    return path
