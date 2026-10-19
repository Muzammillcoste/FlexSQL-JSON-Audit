SELECT
  ROUND(SUM("readings"."payload" -> '$.metrics.energy_kwh'), 2) AS "total_energy_kwh"
FROM "readings"
JOIN "devices"
  ON "readings"."device_id" = "devices"."device_id"
WHERE
  "devices"."site" = 'north' AND "readings"."recorded_at" LIKE '2025-06%'