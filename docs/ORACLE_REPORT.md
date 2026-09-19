# Offline evaluator sensitivity audit

Scored 689 saved distributions and 6590 actions. No model calls.

## Selected actions with a better offered alternative

| Selected kind | n | Original reference | Shallow first | Cleanup first |
|---|---:|---:|---:|---:|
| outer_expansion | 37 | 34/37 (91.9%) | 9/37 (24.3%) | 21/37 (56.8%) |
| nested_expansion | 105 | 50/105 (47.6%) | 45/105 (42.9%) | 41/105 (39.0%) |
| multiply | 49 | 28/49 (57.1%) | 27/49 (55.1%) | 27/49 (55.1%) |
| simplify_product | 264 | 26/264 (9.8%) | 43/264 (16.3%) | 23/264 (8.7%) |
| combine | 59 | 3/59 (5.1%) | 1/59 (1.7%) | 4/59 (6.8%) |

## Probability-distribution metrics

| Evaluator | Quality | Pairwise alignment | Expected regret |
|---|---:|---:|---:|
| reference | 0.835 | 0.725 | 0.780 |
| shallow_first | 0.882 | 0.717 | 0.775 |
| cleanup_first | 0.870 | 0.730 | 0.612 |

These are turn-weighted exploratory summaries, not independent trials. Both alternatives genuinely change local action ordering and balance order. They share the exact algebra implementation; this audits policy sensitivity, not independent arithmetic correctness. Counts remain policy-relative and are not claimed globally optimal.

## Exact small-state search

BFS result statuses: `{'exact': 14}`. Exact means a goal was first discovered in breadth-first order over all engine-generated moves. Search limits lead to explicit censored results. This small tractable subset cannot certify distances for deeply nested expressions.

| Equation | Reference | BFS | Status |
|---|---:|---:|---|
| `x = 5` | 0 | 0 | exact |
| `x = 7/3` | 0 | 0 | exact |
| `(-1)*(x) = (5 + (-2)*(x))` | 1 | 1 | exact |
| `(1/3)*(x) = 7/9` | 1 | 1 | exact |
| `(42)*(x) = 210` | 1 | 1 | exact |
| `x = (-1/69798)*(-162862)` | 1 | 1 | exact |
| `((-1)*(x) + -17171/23266) = (111349/69798 + (-2)*(x))` | 2 | 2 | exact |
| `((18)*(x) + (-4)*(x)) = 70` | 2 | 2 | exact |
| `(-18)*(x) = (-70 + (-4)*(x))` | 2 | 2 | exact |
| `x = (15 + (-2)*(x))` | 2 | 2 | exact |
| `((-1)*(x) + -76031/34899 + -1800/11633) = (-2)*(x)` | 3 | 3 | exact |
| `((42)*(x) + (1)*(-12)) = 198` | 3 | 3 | exact |
| `(86187 + (-1)*(x)) = ((-69799)*(x) + 249049)` | 3 | 3 | exact |
| `86188 = ((-69798)*(x) + 249050)` | 3 | 3 | exact |

## Exact audit of near-completion multiplication choices

Eight selected-multiply states flagged as inferior by the original reference were chosen deterministically by smallest maximum offered reference distance, then current reference distance, episode ID and step. This diagnostic selection targets suspected mistakes and favours tractability; it is not representative of all multiplication choices. BFS applies to each offered action with depth 4 and 1,800-node caps. A censored action is only proved inferior when its rigorous lower bound exceeds a competing exact distance.

| Episode / step | Selected shortest distance or lower bound | Best exact competing distance | Verdict |
|---|---:|---:|---|
| jev_medium_06 / 21 | 2 | 1 | proven_suboptimal |
| jev_medium_06 / 22 | 1 | 1 | proven_optimal |
| jev_unholy_03 / 61 | >=3 | 2 | proven_suboptimal |
| jev_unholy_03 / 67 | >=3 | 1 | proven_suboptimal |
| jev_unholy_06 / 51 | >=3 | 2 | proven_suboptimal |
| jev_medium_02 / 26 | >=3 | 3 | unresolved |
| jev_medium_03 / 17 | >=3 | 3 | unresolved |
| jev_unholy_05 / 61 | >=3 | 2 | proven_suboptimal |

## Interpretation

The outer-expansion disadvantage is strongly evaluator-dependent: 34/37 selected outer expansions have a better offered move under the original policy, versus 9/37 under shallow-first and 21/37 under cleanup-first. The original 91.9% rate therefore cannot substantiate a general outer-expansion weakness. Multiplication is more robust: 28/49 versus 27/49 under either alternative. The targeted BFS audit additionally proves five selected multiplication moves inferior using exact competing distances and exact values or rigorous lower bounds for the selected moves; one flagged move is proven optimal and two remain unresolved under search caps. This targeted subset cannot estimate error prevalence. Exact-distance claims apply only to explicitly exact cases; censored lower bounds can still prove strict inferiority when separated from an exact competitor.

Runtime: 4.3s. See oracle_audit.json and oracle_actions.jsonl for all denominators and counterfactual distances.
