SELECT COUNT(*) FROM orders WHERE json_extract(details,'$.gift_wrap')=1
