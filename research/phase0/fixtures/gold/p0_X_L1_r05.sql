SELECT ROUND(SUM(COALESCE(json_extract(r.payload,'$.metrics.energy_kwh'),
  (SELECT json_extract(x.value,'$.v')/1000.0 FROM json_each(r.payload,'$.data.readings') x WHERE json_extract(x.value,'$.k')='energy'))),2)
FROM readings r JOIN devices d ON d.device_id=r.device_id
WHERE d.site='north' AND r.recorded_at >= '2025-06-01' AND r.recorded_at < '2025-07-01'
