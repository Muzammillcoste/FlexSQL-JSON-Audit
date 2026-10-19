| set | detector | detector_anchor | B1_any_missing | B2_rare_missing | B3_profile_het |
|---|---|---|---|---|---|
| A/B targets (Phase 0) | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 |
| correct runs (Phase 0) | 0/12 | 0/12 | 5/12 | 5/12 | 8/12 |
| E artefacts (Phase 0) | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 |
| benign controls (synthetic) | 5/14 | 0/14 | 14/14 | 10/14 | 14/14 |
| synthetic targets (row-level) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| synthetic target (array-element) | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 |
| held-out targets | 2/2 | 0/2 | 2/2 | 2/2 | 2/2 |
| held-out benign | 2/3 | 0/3 | 2/3 | 1/3 | 3/3 |

Warnings = path-coverage warnings (detector: omitted_structure findings only; parse findings listed separately).

| arm | flagged targets (A/B + synth + held-out) | flagged benign (P0 correct + controls + held-out) | precision | recall on A/B |
|---|---|---|---|---|
| detector | 13/14 | 7/29 | 13/20 | 9/9 |
| detector_anchor | 11/14 | 0/29 | 11/11 | 9/9 |
| B1_any_missing | 13/14 | 21/29 | 13/34 | 9/9 |
| B2_rare_missing | 13/14 | 16/29 | 13/29 | 9/9 |
| B3_profile_het | 14/14 | 25/29 | 14/39 | 9/9 |

| item | group | label | detector | names required path | parse finding | anchor | B1 | B2 | B3 |
|---|---|---|---|---|---|---|---|---|---|
| p0_H01 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_H02 | target_AB | B | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_H03 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_H04 | E_artifact | E | SUSPICIOUS |  | True | SUSPICIOUS | 1 | 1 | 1 |
| p0_H10 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| p0_H_L1_r20 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| p0_H_L2_r20 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| p0_M01 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 0 |
| p0_M02 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 1 |
| p0_M03 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 1 |
| p0_M04 | E_artifact | E | SUSPICIOUS |  | True | SUSPICIOUS | 1 | 1 | 1 |
| p0_M05 | E_artifact | E | SUSPICIOUS |  | True | SUSPICIOUS | 1 | 1 | 1 |
| p0_M_L1_r00 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 0 |
| p0_M_L2_r00 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 0 |
| p0_X01 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| p0_X02 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 1 |
| p0_X03 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X04 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X05 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X06 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 0 |
| p0_X_L1_r01 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X_L1_r05 | target_AB | A | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X_L2_r01 | target_AB | B | SUSPICIOUS* | True | False | SUSPICIOUS* | 1 | 1 | 1 |
| p0_X_L2_r05 | benign | correct | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C01_null_vs_absent | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 0 | 1 |
| C02_optional_bool | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 0 | 1 |
| C03_optional_object | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C04_irrelevant_type_guarded | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C05_irrelevant_type_default | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C06_filtered_before_parse | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C07_filtered_after_parse | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C08_join_restriction | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C09_same_leaf_name | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C10_array_optional_elem_key | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 0 | 1 |
| C11_numeric_strings | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C12_sql_optional | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 0 | 1 |
| C13_sql_irrelevant_type_filter | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| C14_sql_filtered_scope | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| T01_py_rare_legacy | target_synth |  | SUSPICIOUS* |  | False | SUSPICIOUS* | 1 | 1 | 1 |
| T02_sql_rare_legacy | target_synth |  | SUSPICIOUS* |  | False | SUSPICIOUS* | 1 | 1 | 1 |
| T03_array_element_variant | target_elem |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 1 |
| HO1_rare_obs_list | target_synth |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| HO2_complete_handling | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| HO3_optional_allergies | benign |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 0 | 1 |
| HO4_sql_rare_obs | target_synth |  | SUSPICIOUS* |  | False | NO_EVIDENCE | 1 | 1 | 1 |
| HO5_visit_type_counts | benign |  | NO_EVIDENCE |  | False | NO_EVIDENCE | 0 | 0 | 1 |

`*` = path-coverage warning raised (an E item can be SUSPICIOUS from a parse finding alone).
