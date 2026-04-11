-- ============================================================
-- UrbanMove — BigQuery ML Congestion Prediction Model
-- Model type: ARIMA_PLUS (time-series forecasting)
-- Run this after the mobility_events table has at least 24h of data
--
-- Usage:
--   bq query --use_legacy_sql=false < ml/train_model.sql
-- ============================================================

CREATE OR REPLACE MODEL `urbanmove-project-493010.urbanmove.congestion_model`
OPTIONS (
  model_type            = 'ARIMA_PLUS',
  time_series_timestamp_col = 'window_start',
  time_series_data_col  = 'vehicle_count',
  time_series_id_col    = 'zone_id',
  horizon               = 120,          -- forecast up to 120 periods (minutes)
  auto_arima            = TRUE,         -- auto-select p,d,q parameters
  data_frequency        = 'per_minute',
  decompose_time_series = TRUE,         -- extract trend + seasonality
  clean_spikes_and_dips = TRUE,         -- handle outliers automatically
  holiday_region        = 'FR'          -- account for French public holidays
)
AS
SELECT
  DATE_TRUNC(event_ts, MINUTE)          AS window_start,
  zone                                   AS zone_id,
  COUNT(DISTINCT vehicle_id)             AS vehicle_count
FROM
  `urbanmove-project-493010.urbanmove.mobility_events`
WHERE
  event_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND status = 'active'
GROUP BY
  window_start,
  zone_id
ORDER BY
  window_start ASC;
