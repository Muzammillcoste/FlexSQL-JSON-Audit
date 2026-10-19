SELECT ROUND(SUM(COALESCE(json_extract(p.payload,'$.fee'),
 (SELECT json_extract(f.value,'$.amount_cents')/100.0 FROM json_each(p.payload,'$.fees') f WHERE json_extract(f.value,'$.type')='processing'),
 CAST(json_extract(p.payload,'$.pricing.fees.processing') AS REAL))),2)
FROM payment_events p WHERE LOWER(COALESCE(json_extract(p.payload,'$.status'), json_extract(p.payload,'$.state'), json_extract(p.payload,'$.transaction.result.status')))='succeeded' AND UPPER(COALESCE(json_extract(p.payload,'$.currency'), json_extract(p.payload,'$.currency_code'), json_extract(p.payload,'$.transaction.value.currency')))='USD' AND p.created_at < '2025-04-01'
