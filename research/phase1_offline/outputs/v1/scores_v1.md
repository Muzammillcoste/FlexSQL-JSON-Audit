| set | detector | detector_anchor | B1_any_missing | B2_rare_missing | B3_profile_het |
|---|---|---|---|---|---|
| A/B targets (Phase 0) | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 |
| correct runs (Phase 0) | 0/12 | 0/12 | 5/12 | 5/12 | 8/12 |
| E artefacts (Phase 0) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| benign controls (synthetic) | 6/14 | 1/14 | 14/14 | 10/14 | 14/14 |
| synthetic targets (row-level) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| synthetic target (array-element) | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 |
| held-out targets | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| held-out benign | 2/3 | 1/3 | 2/3 | 1/3 | 3/3 |

Warnings = path-coverage warnings (detector: omitted_structure findings only; parse findings listed separately).

| arm | flagged targets (A/B + synth + held-out) | flagged benign (P0 correct + controls + held-out) | precision | recall on A/B |
|---|---|---|---|---|
| detector | 13/14 | 8/29 | 13/21 | 9/9 |
| detector_anchor | 11/14 | 2/29 | 11/13 | 9/9 |
| B1_any_missing | 13/14 | 21/29 | 13/34 | 9/9 |
| B2_rare_missing | 13/14 | 16/29 | 13/29 | 9/9 |
| B3_profile_het | 14/14 | 25/29 | 14/39 | 9/9 |

| item | group | label | detector | names required path | parse finding | anchor | B1 | B2 | B3 |
