SELECT COUNT(*) FROM payment_events p WHERE LOWER(COALESCE(json_extract(p.payload,'$.status'), json_extract(p.payload,'$.state'), json_extract(p.payload,'$.transaction.result.status')))='succeeded' AND LOWER(COALESCE(json_extract(p.payload,'$.card.brand'),
 json_extract(p.payload,'$.payment_method.card.network'), json_extract(p.payload,'$.instrument.details.brand'),
 json_extract(p.payload,'$.instrument.details.card_brand')))='visa'
