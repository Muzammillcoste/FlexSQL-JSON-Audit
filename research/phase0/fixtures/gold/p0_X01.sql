SELECT ROUND(SUM(COALESCE(json_extract(k.value,'$.weight_kg'), json_extract(k.value,'$.gross_weight_kg'),
 json_extract(k.value,'$.weight_g')/1000.0)),1) FROM shipments s, json_each(s.manifest,'$.packages') k WHERE s.created_at LIKE '2025-05-%'
