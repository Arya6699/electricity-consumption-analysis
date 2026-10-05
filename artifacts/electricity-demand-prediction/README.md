# Electricity Consumption Analytics & Demand Prediction

An academic Big Data Analytics project for profiling electricity readings, finding consumption patterns and peak-demand periods, processing large CSV files with PySpark, and predicting future demand with scikit-learn.

## Abstract

Electricity providers need to understand when consumers use energy and anticipate upcoming demand to plan generation and avoid overload. This project provides a web-based workflow for uploading historical consumption data, automatically validating and preparing it, exploring time-based patterns, and comparing machine-learning regressors. Pandas supports interactive profiling and smaller datasets. PySpark demonstrates distributed CSV cleaning and aggregation for larger data; a bounded Spark-processed sample is then passed to scikit-learn for model evaluation and prediction. A React dashboard presents the results and a FastAPI service supplies the analytics API.

## Problem statement

Electricity readings are often stored as large time-stamped CSV files. Manual inspection makes it difficult to detect peak periods, compare weekday and seasonal behavior, prepare imperfect data consistently, and estimate future demand. The project addresses this by providing a repeatable analytics and predictive-forecasting workflow with an interactive interface.

## Objectives

- Accept a user's CSV and profile its columns, types, missing values, and summary statistics.
- Clean duplicate records, parse and sort timestamps, fill missing values, and limit the effect of extreme target outliers.
- Derive hour, day, weekday, week, month, year, weekend, season, and lag features.
- Visualize consumption at multiple time scales and identify high- and low-demand periods.
- Demonstrate PySpark DataFrame ingestion, cleaning, feature generation, and grouped statistics.
- Train and compare Linear Regression, Random Forest, and Gradient Boosting regressors.
- Choose the lowest-RMSE model automatically and report MAE, MSE, RMSE, and R².
- Offer a date-and-time prediction form with optional weather and recent-consumption inputs.

## Existing system

Basic analyses commonly rely on spreadsheets or one-off scripts. They require manual cleanup, are difficult to reproduce, offer limited support for large data, and do not connect analysis results to a usable forecasting dashboard.

## Proposed system

The proposed platform combines a responsive React/Tailwind user interface, a FastAPI analytics service, Pandas/NumPy preprocessing, PySpark scalable processing, scikit-learn model comparison, and SQLite persistence for dataset/model run records. A one-year hourly sample dataset makes the app usable on first launch. Users can replace it with their own CSV.

## System architecture

```text
CSV upload / included sample
          │
          ▼
React + Tailwind pages ── generated typed API client ── /api
  Dashboard · Dataset · Prediction · Models                │
                                                            ▼
                                                   Express route bridge
                                                            │
                                                            ▼
                                                    FastAPI + Pydantic
                                          ┌─────────────────┼───────────────┐
                                          ▼                 ▼               ▼
                                    Pandas / NumPy      PySpark       scikit-learn
                                    clean + profile   distributed     train + predict
                                          └─────────────────┼───────────────┘
                                                            ▼
                                          SQLite results + saved model/CSV
```

The API bridge preserves the shared `/api/electricity/...` path for the hosted preview. FastAPI remains the service that validates requests and performs electricity-specific processing. In standalone local development, Vite proxies `/api` directly to FastAPI.

## Methodology

1. **Ingest:** accept a CSV, check that it is readable, infer a time field and numeric target, and preserve the uploaded source.
2. **Profile:** report row/column counts, original missing-value counts, types, duplicate count, and target summary.
3. **Preprocess:** remove duplicate records, parse dates, discard invalid timestamps, fill missing numeric/categorical values, cap target outliers using IQR bounds, derive time features, and sort chronologically.
4. **Analyze:** aggregate consumption by date, week, month, hour, weekday/weekend, and season; calculate a demand distribution and correlations; identify peak and minimum observations.
5. **Scale:** for a Spark run, read the CSV as a Spark DataFrame, clean and derive features in Spark, perform grouped counts, and hand at most 50,000 cleaned observations to scikit-learn.
6. **Train:** evaluate a chronological holdout (last 20% of observations) using Linear Regression, Random Forest, and Gradient Boosting. Select the lowest-RMSE model.
7. **Predict:** derive calendar and lag values for the requested timestamp; use optional temperature/recent consumption when available; return the demand estimate in the target column's inferred units.

## Modules

| Module | Responsibility |
| --- | --- |
| Data ingestion and profiling | CSV validation, automatic time/target detection, type and missing-value profile, preview |
| Preprocessing | Duplicate removal, datetime conversion, imputation, IQR outlier capping, chronological ordering, feature derivation |
| Exploratory analysis | Trend and grouped series, weekend and seasonal comparisons, distribution, correlation, peak and minimum demand |
| Big Data analytics | PySpark DataFrame ingestion, cleaning, time features, hourly/daily/monthly grouped operations |
| Prediction | Linear Regression, Random Forest, Gradient Boosting, automatic best-model selection, demand prediction |
| Dashboard | Live KPIs, interactive charts and filters, upload/profile views, prediction and model comparison |
| Persistence | SQLite upload/model-run history, saved uploaded CSV, and serialized best model |

## Technologies

- **Frontend:** React, TypeScript, Tailwind CSS, Recharts, TanStack Query, generated OpenAPI client
- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Analytics:** Pandas, NumPy, PySpark, Matplotlib/Seaborn (optional notebook analysis), scikit-learn
- **Storage:** SQLite for processed-result and model-run records; local CSV and joblib files for dataset/model artifacts

## Dataset description and assumptions

The included synthetic demonstration file contains hourly timestamps, electricity consumption in kWh, and temperature in Celsius across a year. It is generated deterministically on first backend startup; it is not presented as a real utility-provider dataset.

Uploaded CSV assumptions:

- One column should contain parseable timestamps. Separate date and hour columns are supported.
- One numeric column should represent consumption, demand, load, energy, power, usage, or electricity. If no name matches, the backend selects the most variable numeric column after excluding common date/index fields.
- Weather is optional. A numeric temperature, weather, humidity, or pressure column is used when detected; it is never required.
- Units are inferred from the target column name (`MWh`, `MW`, `kW`, or default `kWh`). Rename the target column if a different unit should be shown.
- The upload limit is 150 MB. The Spark training path applies distributed cleanup/aggregation and caps the scikit-learn training handoff at 50,000 records.
- For very long histories, the model evaluation is time-ordered: the most recent 20% is held out. Results are recomputed from the active dataset; they are not hardcoded.

## Results

Dataset statistics, visualization values, model metrics, best-model selection, and predictions are calculated from the current uploaded dataset. The Models page displays the current run's MAE, MSE, RMSE, and R² per model, along with a graph of held-out actual and predicted demand. Use the Spark option to display the PySpark processing run and bounded training handoff.

## Conclusion

The project demonstrates an end-to-end electricity analytics pipeline: CSV ingestion, data-quality handling, time-based feature engineering, multiscale analysis, distributed Spark operations, regression model evaluation, and interactive demand forecasting. Its modular API and automatic column detection allow the included sample to be replaced by a compatible real-world CSV.

## Future scope

- Add weather-provider integration after users select a source and authorize access.
- Add forecasting intervals, seasonal cross-validation, hyperparameter tuning, and model drift monitoring.
- Persist multiple datasets and compare regions/meters with dataset workspaces.
- Add an optional sequence model (LSTM) for sufficiently long histories and compare it with the current regressors.
- Add data export, scheduled retraining, and a multi-node Spark deployment profile.

## Installation and run

### Local setup

Requirements: Node.js 20+, pnpm, Python 3.10+, Java 17+ for PySpark.

1. Install Java and Python dependencies:

   ```bash
   # At the repository root
   uv sync
   ```

   Alternatively install the listed Python dependencies with `python -m pip install -r artifacts/electricity-demand-prediction/requirements.txt`.

2. Start FastAPI in terminal 1:

   ```bash
   cd artifacts/electricity-demand-prediction
   uv run --project ../.. python -m uvicorn backend.main:app --app-dir . --reload --host 0.0.0.0 --port 8000
   ```

   Interactive API documentation is available at `http://localhost:8000/docs`.

3. Start the React frontend in terminal 2, from the repository root:

   ```bash
   PORT=5173 BASE_PATH=/ pnpm --filter @workspace/electricity-demand-prediction run dev
   ```

   Open `http://localhost:5173`. Vite forwards `/api/...` calls to the FastAPI process.

### Hosted project preview

Start the **API Server** workflow and the **Electricity Consumption Analytics & Demand Prediction** web workflow. The API Server workflow starts the FastAPI process alongside the shared `/api` service; the web workflow serves the React dashboard.

## How to use

1. **Upload a dataset:** open Dataset, choose a CSV, and select Upload. The interface sends the file contents to `POST /api/electricity/upload`. The backend validates the data, profiles it, cleans it, saves the upload, and refreshes the dataset views.
2. **Review the dashboard:** see total, average, peak, minimum, and predicted next demand. Use the date, month, year, hour, and weekday filters to change the analysis window. Chart values and filters come from the API.
3. **Run Spark processing and train:** open Models and select the PySpark option when available, then train. Spark performs distributed CSV cleanup and time-based grouped operations. Up to 50,000 cleaned rows are used for scikit-learn model fitting.
4. **Compare models:** review MAE, MSE, RMSE, and R² and the actual-versus-predicted series. Lower MAE/MSE/RMSE and higher R² generally indicate a better fit; R² can be negative when the model performs worse than predicting the test-set mean.
5. **Predict demand:** open Prediction, choose a date and hour, optionally enter temperature/recent consumption if known, and request a forecast. Output includes the timestamp, selected model, and inferred unit.
6. **Replace the sample:** upload a CSV containing a parseable date/time field and numeric consumption/demand field. The service automatically detects likely columns, displays the selected target, and adapts optional weather inputs.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/electricity/upload` | Upload and profile CSV text |
| `GET /api/electricity/dataset-info` | Current dataset metadata and profile |
| `GET /api/electricity/dataset-preview` | Preview rows |
| `GET /api/electricity/statistics` | KPI statistics and next-demand estimate |
| `GET /api/electricity/consumption-analysis` | Filtered trend and time-based grouped series |
| `GET /api/electricity/peak-demand` | Peak/minimum and top demand periods |
| `GET /api/electricity/monthly-consumption` | Monthly totals |
| `GET /api/electricity/hourly-consumption` | Hourly average |
| `POST /api/electricity/train-model` | Train and compare regressors; optionally use Spark |
| `GET /api/electricity/model-performance` | Latest model run |
| `POST /api/electricity/predict` | Predict for a date/time |
| `GET /api/electricity/spark-info` | Spark availability and last-run information |
