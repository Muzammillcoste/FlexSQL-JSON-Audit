SELECT COUNT(*) FROM shipments s JOIN carriers c ON c.carrier_code=s.carrier_code WHERE c.transport_mode='sea'
