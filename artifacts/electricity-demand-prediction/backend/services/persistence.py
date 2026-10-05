from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ResultStore:
    """Small local SQLite store for upload history and model evaluation results."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS dataset_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS model_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    best_model TEXT,
                    metrics_json TEXT NOT NULL,
                    spark_used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        return connection

    def record_dataset(self, filename: str, rows: int, summary: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO dataset_events(filename, row_count, summary_json) VALUES (?, ?, ?)",
                (filename, rows, json.dumps(summary)),
            )

    def record_model_run(self, best_model: str | None, metrics: list[dict[str, Any]], spark_used: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO model_runs(best_model, metrics_json, spark_used) VALUES (?, ?, ?)",
                (best_model, json.dumps(metrics), int(spark_used)),
            )
