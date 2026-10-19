SELECT COUNT(*) FROM payment_events p WHERE json_type(p.payload,'$.customer.email')='null' OR json_type(p.payload,'$.customer.contact.email')='null'
