SELECT SUM(json_extract(i.value,'$.qty')) FROM orders o, json_each(o.details,'$.items') i
WHERE o.status='delivered' AND json_extract(i.value,'$.category')='electronics'
