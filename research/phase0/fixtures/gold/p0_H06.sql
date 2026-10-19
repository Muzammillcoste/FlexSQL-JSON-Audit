SELECT COUNT(*) FROM payment_events p WHERE LOWER(COALESCE(json_extract(p.payload,'$.status'), json_extract(p.payload,'$.state'), json_extract(p.payload,'$.transaction.result.status')))='refunded'
