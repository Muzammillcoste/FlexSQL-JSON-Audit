SELECT
  ROUND(SUM("r"."payload" -> '$.metrics.energy_kwh'), 2) AS "total_energy"
FROM "readings" AS "r"
JOIN "devices" AS "d"
  ON "r"."device_id" = "d"."device_id"
WHERE
  "d"."site" = 'north'
  AND "r"."recorded_at" >= '2025-06-01T00:00:00Z'
  AND "r"."recorded_at" < '2025-07-01T00:00:00Z'