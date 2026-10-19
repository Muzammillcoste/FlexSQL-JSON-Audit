SELECT
  COUNT(DISTINCT "customer_id")
FROM "customers"
WHERE
  "segment" = 'enterprise' AND "country" = 'DE'