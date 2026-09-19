# Article claim-to-evidence index

Paths below are relative to the extracted archive. `reproduce.py` verifies the snapshot before running analysis. No published model result is synthesized during reproduction.

| Article claim | Primary evidence | Recalculation |
|---|---|---|
| Example equation and menu | `jev-hypotheses/raw/rollout__rollout_00_nested_chain__original_random__r0__s001.json` | Complete request reconstruction in `tools/verify_results.py`; excerpts shortened only in article |
| 128 fresh states, eight families, 24 saved states | `jev-hypotheses/cases.json`, `protocol.json` | Static analysis cohort membership; families, not states, are clusters |
| Initial 13/16, 9/16, 16/16 completion | `jev-hypotheses/rollouts/*.json`, `rollout_tasks.json` | `analyze_rollouts.py`; article counts also asserted independently |
| Local gains did not establish complete-run gains | `responses/*.json` and initial rollouts | Full static treatment tables plus initial rollout counts; these are separate populations of decisions |
| Eight-cell counts; structured difference −26.5625 points | `rollouts/*.json`, `factorial_rollouts/*.json` | `factorial_rollouts.py --analyze`; subtract within matched case/factor combinations |
| Seven structured case effects negative, one zero | `factorial_rollout_summary.json` | `factor_main_effects.structured.case_effects` |
| Reversal 18.75%, words 6.25% | Frozen label jobs and `responses/*.json` | `analyze_static.py`; fresh side-state semantic cross-repeat averages |
| 6,025 study calls | `raw/*.json`, `budget.json` | `audit_campaign.py`; includes 3,278 static and 2,747 trajectory decisions |
| 0.540718080 USD; combined 0.608268318 USD | Every raw response usage cost, shared ledger and prior ledger | Decimal accounting in `audit_campaign.py`; exact values asserted by public verifier |
| Main figure | Initial 48 rollout episode records | Rebuilt directly by `tools/verify_results.py`; 16 remains the denominator for every policy |
| Evaluator correction | Pilot `raw/`, `steps/` and `probability_scores.jsonl` | `oracle_audit.py`; exact and censored BFS results kept distinct |

The article's proposed uses are hypotheses and have no claimed benchmark support here. The model introduction links the provider's public model page. The dated model identity is additionally verified against all recorded responses.
