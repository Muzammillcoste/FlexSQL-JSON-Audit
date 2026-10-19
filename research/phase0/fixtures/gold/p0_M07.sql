SELECT COUNT(DISTINCT json_extract(i.value,'$.sku')) FROM orders o JOIN customers c ON c.customer_id=o.customer_id,
json_each(o.details,'$.items') i WHERE c.segment='enterprise'
