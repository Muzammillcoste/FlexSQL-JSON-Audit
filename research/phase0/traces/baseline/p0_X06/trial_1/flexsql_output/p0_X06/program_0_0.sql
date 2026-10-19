SELECT
  COUNT(T1."shipment_id")
FROM "shipments" AS T1
INNER JOIN "carriers" AS T2
  ON T1."carrier_code" = T2."carrier_code"
WHERE
  T2."transport_mode" = 'sea'