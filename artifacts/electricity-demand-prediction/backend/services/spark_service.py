from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from .data_service import DatasetState


def spark_availability() -> dict[str, Any]:
    if shutil.which("java") is None:
        return {
            "available": False,
            "version": None,
            "processing_mode": "Pandas",
            "details": "Java is not on PATH. Install a JDK before using the PySpark processing option.",
        }
    try:
        import pyspark

        return {
            "available": True,
            "version": pyspark.__version__,
            "processing_mode": "PySpark local[2]",
            "details": "Spark reads the stored CSV, cleans and aggregates it in distributed DataFrames, then passes a bounded sample to scikit-learn.",
        }
    except Exception as exc:
        return {
            "available": False,
            "version": None,
            "processing_mode": "Pandas",
            "details": f"PySpark could not be imported: {exc}",
        }


def clean_and_sample_with_spark(
    csv_path: Path,
    state: DatasetState,
    max_training_rows: int = 50_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the CSV cleaning and aggregations in Spark; bound only the ML handoff."""
    from pyspark.sql import SparkSession, functions as F

    if shutil.which("java") is None:
        raise RuntimeError("Java is required for PySpark. Install a JDK and restart the backend.")
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("ElectricityDemandAnalytics")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        raw = spark.read.option("header", True).option("inferSchema", True).csv(str(csv_path))
        original_rows = raw.count()
        timestamp_col = state.datetime_column
        if " + " in timestamp_col:
            date_col, hour_col = timestamp_col.split(" + ")
            raw = raw.withColumn(
                "_event_time",
                F.to_timestamp(
                    F.concat_ws(
                        " ",
                        F.col(date_col).cast("string"),
                        F.concat(F.col(hour_col).cast("string"), F.lit(":00:00")),
                    )
                ),
            )
        else:
            raw = raw.withColumn("_event_time", F.to_timestamp(F.col(timestamp_col)))
        raw = raw.withColumn("_demand", F.col(state.target_column).cast("double"))
        raw = raw.dropna(subset=["_event_time", "_demand"]).dropDuplicates()
        bounds = raw.approxQuantile("_demand", [0.25, 0.75], 0.01)
        if len(bounds) == 2 and bounds[1] > bounds[0]:
            iqr = bounds[1] - bounds[0]
            raw = raw.filter(
                (F.col("_demand") >= bounds[0] - 1.5 * iqr)
                & (F.col("_demand") <= bounds[1] + 1.5 * iqr)
            )
        cleaned_rows = raw.count()
        featured = (
            raw.withColumn("hour", F.hour("_event_time"))
            .withColumn("day", F.dayofmonth("_event_time"))
            .withColumn("day_of_week", F.dayofweek("_event_time"))
            .withColumn("week", F.weekofyear("_event_time"))
            .withColumn("month", F.month("_event_time"))
            .withColumn("year", F.year("_event_time"))
            .withColumn("is_weekend", F.dayofweek("_event_time").isin([1, 7]).cast("int"))
        )
        hourly_count = featured.groupBy("hour").count().count()
        daily_count = featured.groupBy(F.to_date("_event_time").alias("day")).count().count()
        monthly_count = featured.groupBy(F.date_format("_event_time", "yyyy-MM").alias("month")).count().count()
        sampled = featured
        if cleaned_rows > max_training_rows:
            sampled = featured.orderBy(F.rand(seed=31)).limit(max_training_rows)
        sample_pdf = sampled.select("_event_time", "_demand").toPandas()
        sample_pdf = sample_pdf.rename(columns={"_event_time": "_timestamp", "_demand": "_target"})
        sample_pdf["timestamp"] = sample_pdf["_timestamp"]
        sample_pdf[state.target_column] = sample_pdf["_target"]
        weather_name = next(
            (
                column
                for column in state.frame.columns
                if not column.startswith("_") and column in raw.columns
                and any(hint in column.lower() for hint in ("temp", "weather", "humidity", "pressure"))
            ),
            None,
        )
        if weather_name:
            weather = sampled.select("_event_time", F.col(weather_name).cast("double").alias(weather_name)).toPandas()
            sample_pdf = sample_pdf.merge(
                weather.rename(columns={"_event_time": "_timestamp"}),
                on="_timestamp",
                how="left",
            )
        report = {
            "version": spark.version,
            "input_rows": int(original_rows),
            "cleaned_rows": int(cleaned_rows),
            "hourly_groups": int(hourly_count),
            "daily_groups": int(daily_count),
            "monthly_groups": int(monthly_count),
            "training_rows_sent_to_sklearn": len(sample_pdf),
        }
        return sample_pdf.sort_values("_timestamp").reset_index(drop=True), report
    finally:
        spark.stop()
