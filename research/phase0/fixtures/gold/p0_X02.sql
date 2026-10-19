SELECT (SELECT COALESCE(SUM(json_extract(i.value,'$.qty')),0) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code,
  json_each(s.manifest,'$.packages') k, json_each(k.value,'$.items') i WHERE c.carrier_name='FastFreight')
 + (SELECT COALESCE(SUM(json_extract(i.value,'$.qty')),0) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code,
  json_each(s.manifest,'$.packages') k, json_each(k.value,'$.boxes') b, json_each(b.value,'$.items') i WHERE c.carrier_name='FastFreight')
