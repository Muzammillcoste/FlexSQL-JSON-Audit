SELECT COUNT(*) FROM readings r JOIN devices d ON d.device_id=r.device_id
WHERE d.model='TX-200' AND r.recorded_at >= '2025-07-01' AND r.recorded_at < '2025-08-01'
AND LOWER(COALESCE(json_extract(r.payload,'$.status'), json_extract(r.payload,'$.state.code')))='fault'
