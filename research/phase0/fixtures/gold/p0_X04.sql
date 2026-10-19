SELECT ROUND(AVG((COALESCE(
  (SELECT unixepoch(json_extract(e.value,'$.at')) FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED'),
  (SELECT json_extract(c.value,'$.ts')/1000 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered'))
  - unixepoch(s.created_at))/3600.0),1)
FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code WHERE c.transport_mode='air'
AND COALESCE((SELECT 1 FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED'),
             (SELECT 1 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered')) = 1
