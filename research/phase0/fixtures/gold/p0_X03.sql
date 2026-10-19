SELECT COUNT(*) FROM shipments s WHERE s.created_at LIKE '2025-06-%' AND (
 EXISTS (SELECT 1 FROM json_each(s.tracking,'$.events') e WHERE json_extract(e.value,'$.code')='DELIVERED') OR
 EXISTS (SELECT 1 FROM json_each(s.tracking,'$.history.checkpoints') c WHERE json_extract(c.value,'$.status')='delivered'))
