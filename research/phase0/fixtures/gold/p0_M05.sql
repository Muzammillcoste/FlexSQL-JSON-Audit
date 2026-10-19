SELECT COUNT(*) FROM orders WHERE status='delivered' AND json_extract(details,'$.shipping.address.city')='Lyon'
