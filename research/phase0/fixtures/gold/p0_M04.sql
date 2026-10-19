SELECT COUNT(*) FROM orders WHERE json_type(details,'$.coupon')='object'
