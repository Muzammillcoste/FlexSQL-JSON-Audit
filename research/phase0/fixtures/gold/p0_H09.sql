SELECT COUNT(*) FROM payment_events p JOIN merchants m ON m.merchant_id=p.merchant_id WHERE m.region='APAC' AND p.created_at LIKE '2025-02-%'
