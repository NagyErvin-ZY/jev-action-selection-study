# Static controlled hypothesis experiment

**All frozen static jobs have terminal records**. 3278/3278 jobs returned scored results; 0 missing and 0 failed/cut off.

All effects below average the two repeats within a state, then average states within templates, then weight templates equally. Intervals resample whole templates (4,000 bootstrap samples). There are only eight fresh template clusters, four in each predesignated split, so intervals are exploratory and may understate uncertainty about unseen equation families. No model was trained and no treatment was selected using held-out results. Saved states are a diagnostic selection from earlier runs, not a representative fresh benchmark. Saved-state means weight the three original equations (simple, medium, unholy) equally, and intervals resample those three source-equation clusters. These saved intervals are especially fragile; fifteen episodes do not provide fifteen independent problem clusters.

## Paired prompt effects

Main effects average across the other two prompt factors. Combined compares all three interventions with the original prompt. Positive quality changes favour the treatment; negative regret changes favour it. Quality excludes reroll/completion and renormalizes algebra-action probabilities, so reroll mass is analysed separately. Equal-quality menus have undefined quality and are omitted rather than assigned a score.

| Cohort | Evaluator | Treatment | Δ probability quality [95% cluster interval] | Δ regret, steps |
|---|---|---|---:|---:|
| fresh | reference | neutral | -0.015 [-0.034, +0.003] | +0.046 [-0.042, +0.135] |
| fresh | reference | structured | -0.000 [-0.035, +0.029] | -0.023 [-0.160, +0.127] |
| fresh | reference | guided | +0.045 [+0.032, +0.062] | -0.223 [-0.272, -0.188] |
| fresh | reference | combined | +0.029 [-0.005, +0.059] | -0.198 [-0.366, -0.023] |
| fresh | shallow_first | neutral | -0.006 [-0.027, +0.010] | -0.013 [-0.144, +0.125] |
| fresh | shallow_first | structured | +0.008 [-0.009, +0.024] | -0.150 [-0.285, -0.017] |
| fresh | shallow_first | guided | +0.032 [+0.021, +0.046] | -0.225 [-0.282, -0.173] |
| fresh | shallow_first | combined | +0.034 [+0.010, +0.059] | -0.391 [-0.658, -0.133] |
| fresh | cleanup_first | neutral | -0.009 [-0.023, +0.005] | +0.009 [-0.057, +0.079] |
| fresh | cleanup_first | structured | +0.000 [-0.029, +0.027] | -0.034 [-0.162, +0.097] |
| fresh | cleanup_first | guided | +0.024 [+0.017, +0.032] | -0.129 [-0.151, -0.105] |
| fresh | cleanup_first | combined | +0.016 [-0.017, +0.046] | -0.153 [-0.326, +0.024] |
| diagnostic | reference | combined | +0.013 [-0.039, +0.062] | -0.122 [-0.391, +0.147] |
| diagnostic | shallow_first | combined | +0.019 [-0.015, +0.057] | -0.187 [-0.576, +0.100] |
| diagnostic | cleanup_first | combined | +0.000 [-0.053, +0.054] | -0.078 [-0.377, +0.197] |
| heldout | reference | combined | +0.045 [+0.020, +0.072] | -0.275 [-0.402, -0.110] |
| heldout | shallow_first | combined | +0.049 [+0.032, +0.076] | -0.596 [-0.809, -0.312] |
| heldout | cleanup_first | combined | +0.031 [+0.011, +0.055] | -0.229 [-0.337, -0.082] |
| saved | reference | combined | -0.008 [-0.094, +0.049] | -0.029 [-0.187, +0.201] |
| saved | shallow_first | combined | -0.008 [-0.094, +0.051] | -0.086 [-0.321, +0.201] |
| saved | cleanup_first | combined | -0.007 [-0.094, +0.049] | -0.049 [-0.247, +0.201] |

## Structure and prompt interactions

Structural comparisons match the other three assigned factors within a template. Baseline is the structural effect under the original prompt; other columns measure how that structural contrast changes the prompt treatment effect. Depth also changes node count and horizon; width has template-dependent meaning. Each structural state has its own action pool and one independently generated menu, so contrasts also include induced menu availability and scoring-scale changes. They cannot identify a pure depth or internal-representation mechanism. Magnitude and rational regime change literal values, and rational regime also changes the constructed root. These factors therefore identify the defined interventions, not isolated internal mechanisms.

| Factor (high − low) | Evaluator | Baseline quality difference | Interaction with combined prompt |
|---|---|---:|---:|
| nesting | reference | -0.068 [-0.119, -0.026] | +0.087 [+0.041, +0.138] |
| nesting | shallow_first | -0.077 [-0.134, -0.035] | +0.052 [+0.014, +0.091] |
| nesting | cleanup_first | +0.006 [-0.044, +0.048] | +0.068 [+0.031, +0.108] |
| branch_width | reference | +0.011 [-0.053, +0.084] | -0.009 [-0.052, +0.036] |
| branch_width | shallow_first | +0.003 [-0.063, +0.073] | -0.007 [-0.045, +0.029] |
| branch_width | cleanup_first | +0.033 [-0.018, +0.097] | -0.012 [-0.053, +0.027] |
| magnitude | reference | +0.042 [-0.033, +0.110] | +0.003 [-0.032, +0.036] |
| magnitude | shallow_first | +0.007 [-0.035, +0.051] | +0.002 [-0.026, +0.028] |
| magnitude | cleanup_first | +0.052 [+0.001, +0.105] | -0.015 [-0.048, +0.021] |
| numeric_regime | reference | -0.181 [-0.285, -0.086] | +0.081 [+0.018, +0.134] |
| numeric_regime | shallow_first | -0.148 [-0.258, -0.046] | +0.087 [+0.051, +0.128] |
| numeric_regime | cleanup_first | -0.182 [-0.280, -0.100] | +0.094 [+0.040, +0.144] |

Baseline-menu availability helps assess one structural confound. Equal-template summaries use the original reference evaluator; they are descriptive, not controls that make menus identical.

| Factor | Level | Fraction of menus with an improving move | Mean fraction of algebra moves improving |
|---|---|---:|---:|
| nesting | low | 0.906 | 0.202 |
| nesting | high | 0.875 | 0.174 |
| branch_width | low | 0.844 | 0.148 |
| branch_width | high | 0.938 | 0.229 |
| magnitude | low | 0.891 | 0.187 |
| magnitude | high | 0.891 | 0.189 |
| numeric_regime | low | 0.891 | 0.191 |
| numeric_regime | high | 0.891 | 0.186 |

## Menus, history, and padding

Menu changes are assessed against the best move in the full available action pool, not the best offered move. This prevents an easier or weaker offered menu from manufacturing a normalized-quality improvement. The cover-best intervention guarantees an original-reference-best move, not the optimum under every evaluator. Full-pool regret is conditional on algebra moves and cannot by itself value the future benefit of reroll. Padding changes archival content and attention placement as well as length. Removing history is evaluated only on saved states with nonempty history.

| Kind / condition | Cohort | Δ full-pool regret (menu) or Δ quality (history) | Δ reroll probability |
|---|---|---:|---:|
| menu: cover_best | fresh | -0.367 [-1.024, +0.251] | -0.029 [-0.078, +0.000] |
| menu: cover_best | saved | -0.634 [-0.806, -0.506] | -0.118 [-0.271, +0.000] |
| menu: cover_four | fresh | -1.149 [-2.499, +0.035] | -0.033 [-0.081, -0.007] |
| menu: cover_four | saved | -0.735 [-0.911, -0.582] | -0.121 [-0.271, -0.003] |
| menu: omit_improving | fresh | +1.185 [-0.118, +2.357] | +0.047 [-0.023, +0.121] |
| menu: omit_improving | saved | +1.336 [+0.627, +1.796] | +0.214 [+0.152, +0.275] |
| history: none | saved | -0.024 [-0.052, -0.004] | -0.036 [-0.077, -0.004] |
| history: padding_2000_prefix | fresh | -0.006 [-0.015, +0.006] | +0.009 [+0.005, +0.013] |
| history: padding_2000_prefix | saved | -0.004 [-0.007, +0.000] | +0.001 [+0.000, +0.002] |
| history: padding_2000_suffix | fresh | +0.007 [-0.001, +0.015] | +0.009 [+0.003, +0.018] |
| history: padding_2000_suffix | saved | -0.002 [-0.014, +0.004] | +0.003 [-0.004, +0.012] |
| history: padding_6000_prefix | fresh | -0.006 [-0.018, +0.010] | +0.014 [+0.008, +0.021] |
| history: padding_6000_prefix | saved | -0.001 [-0.011, +0.012] | +0.010 [+0.000, +0.030] |
| history: padding_6000_suffix | fresh | +0.000 [-0.007, +0.008] | +0.012 [+0.006, +0.022] |
| history: padding_6000_suffix | saved | -0.005 [-0.017, +0.003] | -0.002 [-0.015, +0.006] |

## Labels and identical-repeat noise

All distribution comparisons use the full reported distribution and map labels back to exact semantic action keys, including reroll/completion. Each label treatment averages all four baseline-versus-treatment repeat pairs. Identical-repeat noise uses the two baseline responses on exactly the same side-test cases; unknown provider caching means this is observed repeat variability, not a pure estimate of intrinsic model stochasticity; averaging distributions before comparing would artificially suppress this noise. Total variation is 0 for identical distributions and 1 for disjoint distributions; Jensen–Shannon divergence uses base-2 logarithms. Fresh identical-repeat choices flipped on 0 of 16 states. Its degenerate bootstrap interval does not establish zero underlying variation: a tiny sample with no observed event cannot estimate rare-event uncertainty through ordinary resampling.

| Condition | Cohort | Semantic total variation | Choice-flip rate |
|---|---|---:|---:|
| identical_repeat | fresh | +0.033 [+0.021, +0.047] | +0.000 (degenerate bootstrap; uncertainty unresolved) |
| identical_repeat | saved | +0.025 [+0.013, +0.042] | +0.083 [+0.000, +0.125] |
| reverse | fresh | +0.136 [+0.118, +0.154] | +0.188 [+0.062, +0.375] |
| reverse | saved | +0.092 [+0.069, +0.130] | +0.146 [+0.062, +0.312] |
| words | fresh | +0.049 [+0.039, +0.061] | +0.062 [+0.000, +0.156] |
| words | saved | +0.038 [+0.027, +0.057] | +0.042 [+0.000, +0.062] |
| words_reverse | fresh | +0.135 [+0.108, +0.165] | +0.219 [+0.031, +0.469] |
| words_reverse | saved | +0.087 [+0.057, +0.116] | +0.104 [+0.062, +0.125] |

## Confidence is not correctness calibration

The following is the rate of selecting an algebra action with worse reference cost than another offered action. It excludes reroll and completion selections. Bins condition on the probability assigned to the selected action; they are an error association, not calibration against a true target probability distribution. The number of eligible observations and contributing clusters changes by bin.

| Prompt | Cohort | Selected probability bin | Suboptimal rate [cluster interval] | Algebra observations |
|---|---|---|---:|---:|
| n0_s0_g0 | fresh | [0, 0.5] | +0.603 [+0.392, +0.790] | 112 |
| n0_s0_g0 | fresh | [0.5, 0.8] | +0.410 [+0.201, +0.637] | 105 |
| n0_s0_g0 | fresh | [0.8, 1] | +0.354 [+0.083, +0.625] | 37 |
| n0_s0_g0 | saved | [0, 0.5] | +0.250 [+0.000, +0.500] | 9 |
| n0_s0_g0 | saved | [0.5, 0.8] | +0.111 [+0.000, +0.333] | 12 |
| n0_s0_g0 | saved | [0.8, 1] | +0.067 [+0.000, +0.200] | 19 |
| n1_s1_g1 | fresh | [0, 0.5] | +0.522 [+0.382, +0.670] | 134 |
| n1_s1_g1 | fresh | [0.5, 0.8] | +0.390 [+0.199, +0.589] | 100 |
| n1_s1_g1 | fresh | [0.8, 1] | +0.417 [+0.083, +0.750] | 20 |
| n1_s1_g1 | saved | [0, 0.5] | +0.200 [+0.000, +0.400] | 11 |
| n1_s1_g1 | saved | [0.5, 0.8] | +0.333 [+0.000, +0.500] | 12 |
| n1_s1_g1 | saved | [0.8, 1] | +0.000 (degenerate bootstrap; uncertainty unresolved) | 17 |

## Evaluator and measurement limits

All three evaluators are deterministic policies, not general shortest-path oracles. A prompt effect that changes sign across evaluators is strategy-sensitive evidence. Strict pair reversals and tie disagreements below quantify this sensitivity; the separate oracle audit additionally tests tractable bounded shortest paths. These external behavioural tests cannot identify a specific internal architectural cause.

| Alternative evaluator | Strict pair reversals / comparable pairs | Equal-cluster reversal rate | Tie disagreements |
|---|---:|---:|---:|
| shallow_first | 123/4714 | +0.022 [+0.008, +0.038] | 271 |
| cleanup_first | 66/4651 | +0.012 [+0.005, +0.020] | 275 |

## Audit

```json
{
  "expected_jobs": 3278,
  "terminal_jobs": 3278,
  "successful_jobs": 3278,
  "failed_jobs": 0,
  "missing_jobs": 0,
  "statuses": {
    "ok": 3278
  },
  "statuses_by_kind": {
    "core": {
      "ok": 2432
    },
    "menu": {
      "ok": 240
    },
    "labels": {
      "ok": 240
    },
    "history": {
      "ok": 366
    }
  },
  "incomplete_successful_repeat_pairs": 0,
  "undefined_quality_by_evaluator": {
    "reference": 2,
    "shallow_first": 2,
    "cleanup_first": 2
  },
  "billed_input_token_range": [
    1046,
    11461
  ],
  "billed_input_token_median": 1736.0,
  "static_response_cost_usd": 0.322986552,
  "cost_note": "Successful response cost only. Shared budget ledger is authoritative and also includes failures/retries and rollouts.",
  "missing_ids": [],
  "failed_ids": []
}
```

All condition summaries, cluster contributions, structural interactions, actual input-token changes, and evaluator variants are retained in `static_summary.json`. No p-values or data-dependent significance filtering are used. Successful paired measurements alone enter effects; missing, failed, and cutoff responses stay in the audit. No missing result is imputed. Analyses with incomplete repeat pairs are omitted. The reports cover the frozen hypotheses; they do not establish performance over algebra generally.
