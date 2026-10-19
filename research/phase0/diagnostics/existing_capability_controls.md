# Existing-capability controls (tool level, no LLM)

Each cell: fraction of the case's required alternative structures revealed by the upstream `query_database` output (random-sample controls: mean over 20 seeds of the per-structure discovery indicator, worst structure shown); in brackets the output size in characters (~chars/4 tokens).

| case | C1_first_5 | C1_first_20 | C1_first_100 | C1r_random_20 | C1r_random_100 | C2_path_enum | C3_path_freq |
|---|---|---|---|---|---|---|---|
| p0_H01 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H02 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 0.50 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H03 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H04 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H05 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H06 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H10 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 1.00 [5204] | 1.00 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_H_L1_r20 | 1.00 [711] | 1.00 [2523] | 1.00 [12163] | 1.00 [2452] | 1.00 [12015] | 1.00 [231] | 1.00 [305] |
| p0_H_L2_r20 | 1.00 [711] | 1.00 [2523] | 1.00 [12163] | 1.00 [2452] | 1.00 [12015] | 1.00 [231] | 1.00 [305] |
| p0_X01 | 0.00 [2740] | 0.00 [9790] | 1.00 [51171] | 0.60 [4049] | 0.95 [20007] | 1.00 [598] | 1.00 [742] |
| p0_X02 | 1.00 [2740] | 1.00 [9790] | 1.00 [51171] | 0.60 [4049] | 0.95 [20007] | 1.00 [598] | 1.00 [742] |
| p0_X03 | 0.00 [2740] | 0.00 [9790] | 0.00 [51171] | 0.95 [4049] | 1.00 [20007] | 1.00 [598] | 1.00 [742] |
| p0_X04 | 0.00 [2740] | 0.00 [9790] | 0.00 [51171] | 0.95 [4049] | 1.00 [20007] | 1.00 [598] | 1.00 [742] |
| p0_X05 | 0.00 [1154] | 0.00 [4353] | 0.00 [22626] | 0.15 [5204] | 0.50 [25739] | 1.00 [841] | 1.00 [1057] |
| p0_X_L1_r01 | 0.00 [569] | 0.00 [2168] | 1.00 [10745] | 0.20 [2183] | 0.70 [10764] | 1.00 [231] | 1.00 [301] |
| p0_X_L1_r05 | 0.00 [569] | 0.00 [2168] | 1.00 [10816] | 0.75 [2240] | 0.90 [11023] | 1.00 [231] | 1.00 [305] |
| p0_X_L2_r01 | 0.00 [569] | 0.00 [2168] | 1.00 [10745] | 0.20 [2183] | 0.70 [10764] | 1.00 [231] | 1.00 [301] |
| p0_X_L2_r05 | 0.00 [569] | 0.00 [2168] | 1.00 [10816] | 0.75 [2240] | 0.90 [11023] | 1.00 [231] | 1.00 [305] |

## Example: C3 path-frequency output for fleet_r01.readings.payload (as the agent would see it)
```
1 example rows:
| json_path | n_rows |
| --- | --- |
| $.fw | 4000 |
| $.status | 3960 |
| $.metrics."temp_c" | 3960 |
| $.metrics."humidity_pct" | 3960 |
| $.metrics."energy_kwh" | 3960 |
| $.state.code | 40 |
| $.data.readings[*].v | 40 |
| $.data.readings[*].u | 40 |
| $.data.readings[*].k | 40 |

```

## Example: C3 path-frequency output for payments.payment_events.payload
```
1 example rows:
| json_path | n_rows |
| --- | --- |
| $.object | 2083 |
| $.customer.id | 2083 |
| $.status | 1115 |
| $.fee | 1115 |
| $.currency | 1115 |
| $.card.last4 | 1115 |
| $.card.brand | 1115 |
| $.amount | 1115 |
| $.state | 968 |
| $.fees[*].type | 968 |
| $.fees[*]."amount_cents" | 968 |
| $.customer.email | 968 |
| $."payment_method".type | 968 |
| $."payment_method".card.network | 968 |
| $."payment_method".card.last4 | 968 |
| $."currency_code" | 968 |
| $."amount_cents" | 943 |
| $.transaction.value.currency | 417 |
| $.transaction.value.amount | 417 |
| $.transaction.result.status | 417 |
| $.pricing.fees.processing | 417 |
| $.pricing.fees.fx | 417 |
| $.instrument.kind | 417 |
| $.customer.ref | 417 |
| $.customer.contact.locale | 417 |
| $.customer.contact.email | 351 |
| $.instrument.details.last4 | 319 |
| $.instrument.details.brand | 319 |
| $.instrument.details.provider | 98 |
| $.instrument.details."card_brand" | 98 |
| $.platform | 25 |
| $.charges.data[*].captured | 25 |
| $.charges.data[*]."amount_cents" | 25 |

```
