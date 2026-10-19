SELECT ROUND(AVG(CAST(json_extract(details,'$.shipping.cost') AS REAL)),2) FROM orders WHERE json_extract(details,'$.shipping.method')='express'
