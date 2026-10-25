-- One-time setup for gift card listing history.
-- bq query --project_id=vigila-d6c82 --location=us-central1 --use_legacy_sql=false < bigquery_schema.sql

CREATE SCHEMA IF NOT EXISTS `vigila-d6c82.vigila`
OPTIONS (location = 'us-central1');

CREATE TABLE IF NOT EXISTS `vigila-d6c82.vigila.giftcard_listings` (
  run_id     STRING    NOT NULL,
  run_ts     TIMESTAMP NOT NULL,
  platform   STRING    NOT NULL,
  brand      STRING    NOT NULL,
  face_value FLOAT64   NOT NULL,
  discount   FLOAT64   NOT NULL OPTIONS (description = 'Discount percent, e.g. 7.5 = 7.5% off')
)
PARTITION BY DATE(run_ts)
CLUSTER BY brand, platform
OPTIONS (partition_expiration_days = 548);  -- 18 months
