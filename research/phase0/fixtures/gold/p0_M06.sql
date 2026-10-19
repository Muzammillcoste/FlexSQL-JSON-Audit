SELECT ROUND(SUM(json_extract(i.value,'$.qty')*json_extract(i.value,'$.unit_price')),2)
FROM orders o, json_each(o.details,'$.items') i WHERE o.order_date LIKE '2025-03-%'
