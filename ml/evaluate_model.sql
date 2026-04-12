-- ============================================================
-- UrbanMove — BigQuery ML Model Evaluation
-- Run after train_model.sql to get performance metrics
--
-- Usage:
--   bq query --use_legacy_sql=false < ml/evaluate_model.sql
-- ============================================================

-- 1. ARIMA_PLUS model quality metrics per zone
--    ML.EVALUATE for time-series models returns model-selection metrics,
--    not MAE/RMSE.  Lower AIC = better fit; higher log_likelihood = better fit.
SELECT
  zone_id,
  non_seasonal_p  AS p,
  non_seasonal_d  AS d,
  non_seasonal_q  AS q,
  ROUND(AIC, 4)              AS aic,
  ROUND(log_likelihood, 4)   AS log_likelihood,
  ROUND(variance, 6)         AS variance,
  seasonal_periods,
  has_holiday_effect,
  has_spikes_and_dips
FROM
  ML.EVALUATE(MODEL `urbanmove-project-493010.urbanmove.congestion_model`)
ORDER BY
  AIC ASC;

-- 2. Sample 30-minute forecast for Paris 1er
SELECT
  forecast_timestamp,
  zone_id,
  ROUND(forecast_value, 2)                       AS predicted_vehicles,
  ROUND(prediction_interval_lower_bound, 2)      AS lower_90,
  ROUND(prediction_interval_upper_bound, 2)      AS upper_90
FROM
  ML.FORECAST(
    MODEL `urbanmove-project-493010.urbanmove.congestion_model`,
    STRUCT(30 AS horizon, 0.9 AS confidence_level)
  )
WHERE
  zone_id = 'Paris-1er'
ORDER BY
  forecast_timestamp ASC;

-- 3. Decomposed components (trend + seasonality) for insight
SELECT
  time_series_timestamp,
  zone_id,
  ROUND(trend, 3)      AS trend,
  ROUND(seasonal_period_yearly, 3)  AS seasonal_yearly,
  ROUND(seasonal_period_weekly, 3)  AS seasonal_weekly,
  ROUND(seasonal_period_daily, 3)   AS seasonal_daily
FROM
  ML.EXPLAIN_FORECAST(
    MODEL `urbanmove-project-493010.urbanmove.congestion_model`,
    STRUCT(30 AS horizon, 0.9 AS confidence_level)
  )
WHERE zone_id = 'Paris-1er'
ORDER BY time_series_timestamp DESC
LIMIT 10;
