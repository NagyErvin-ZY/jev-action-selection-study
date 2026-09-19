# Fresh equation rollout confirmation

**Complete frozen confirmation set: 48 episodes on eight fresh equations.**

All completed trajectories were replayed from their frozen starting AST. Every action preserved the exact rational root. Every reported solution ended literally `x = exact_root`. This validation checks the algebra engine and outcome records; the model selects operations and the engine performs arithmetic.

Three policies were fixed before inference: original prompt with random menus, combined prompt with random menus, and combined prompt with one best-reference-cost action guaranteed in each menu. The combined prompt joins neutral operation wording, structured expression presentation, and explicit strategy guidance. It was prespecified rather than chosen as the best arm after looking at results.

| Policy | Solved | Mean decisions to stop, all | Median decisions, successes only | Mean completion-budget score |
|---|---:|---:|---:|---:|
| Original prompt · random menu | 13/16 | 20.25 | 22.00 | 27.50 |
| Combined prompt · random menu | 9/16 | 18.69 | 14.00 | 35.50 |
| Combined prompt · best move covered | 16/16 | 14.62 | 14.00 | 14.62 |

**An early cutoff is not a fast solution.** Decisions to stop describe resources consumed, including failed attempts. Successful-only step counts condition on success and can be selection-biased. Completion-budget score assigns each solved episode its actual decisions and each unsolved episode its common, predeclared case decision cap. It is a conservative evaluation penalty, not invented continuation data or an estimate of how many steps a failed run would eventually need.

## Paired comparisons

Pairs share the same case and repeat seed. Menus are coupled only while states and random-menu generation remain identical; once actions diverge, future menus differ. The coverage policy deliberately changes the menu generator.

### Combined prompt · random menu versus Original prompt · random menu

- Matched episodes: **16**. Rescued failures: **1**. Regressed successes: **5**. Both solved: **8**. Neither solved: **2**.
- Cases with at least one rescue: **1**; at least one regression: **4**. These sets can overlap across repeats. Net improved cases: **1**; net regressed cases: **4**.
- Equal-case mean solve-rate difference: **-25.00 percentage points**.
- Mean treatment minus control decisions among jointly solved pairs: **-1.00** (negative favours treatment).
- Equal-case mean completion-budget-score difference: **8.00** (negative favours treatment).

### Combined prompt · best move covered versus Combined prompt · random menu

- Matched episodes: **16**. Rescued failures: **7**. Regressed successes: **0**. Both solved: **9**. Neither solved: **0**.
- Cases with at least one rescue: **5**; at least one regression: **0**. These sets can overlap across repeats. Net improved cases: **5**; net regressed cases: **0**.
- Equal-case mean solve-rate difference: **43.75 percentage points**.
- Mean treatment minus control decisions among jointly solved pairs: **-5.44** (negative favours treatment).
- Equal-case mean completion-budget-score difference: **-20.88** (negative favours treatment).

### Combined prompt · best move covered versus Original prompt · random menu

- Matched episodes: **16**. Rescued failures: **3**. Regressed successes: **0**. Both solved: **13**. Neither solved: **0**.
- Cases with at least one rescue: **2**; at least one regression: **0**. These sets can overlap across repeats. Net improved cases: **2**; net regressed cases: **0**.
- Equal-case mean solve-rate difference: **18.75 percentage points**.
- Mean treatment minus control decisions among jointly solved pairs: **-8.77** (negative favours treatment).
- Equal-case mean completion-budget-score difference: **-12.88** (negative favours treatment).

## Held-out templates

| Policy | Diagnostic solved | Held-out solved |
|---|---:|---:|
| Original prompt · random menu | 7/8 | 6/8 |
| Combined prompt · random menu | 7/8 | 2/8 |
| Combined prompt · best move covered | 8/8 | 8/8 |

There are eight distinct equations and eight template clusters, four reserved as held-out before model calls. Two repeats per equation are not two independent equation families. Descriptive paired counts and equal-case means are primary here; these small samples do not justify a broad-domain capability claim.

## Stopping reasons

| Policy | Reason | Episodes |
|---|---|---:|
| Original prompt · random menu | cutoff_stagnation | 3 |
| Original prompt · random menu | solved | 13 |
| Combined prompt · random menu | cutoff_reroll_streak | 1 |
| Combined prompt · random menu | cutoff_stagnation | 6 |
| Combined prompt · random menu | solved | 9 |
| Combined prompt · best move covered | solved | 16 |

## Interpretation

The combined prompt reduced observed fresh-equation solve rate under the same random-menu policy in this confirmation set. A stronger local distribution score would therefore not, on its own, establish a better end-to-end controller.

The guaranteed-coverage policy uses the reference evaluator to ensure a best-scored action is offered. Any rescue in that arm demonstrates the value of algorithmic menu support. It must not be attributed to an improvement in the model itself, and comparison with the combined-random arm isolates the change in menu policy more directly than comparison with the original prompt.

Reference distance is remaining work under a fixed deterministic strategy, not a proven globally shortest path. Trajectory plots show every observed decision, including rerolls; they stop at actual terminal points and use explicit failure markers. The cumulative-completion chart keeps failures in the denominator and reports observed completion fractions, not a Kaplan–Meier estimate relying on independent censoring.

## Files and cost

Recorded valid-decision cost: **$0.06887941**. This would exclude any charged request without a logged action; the final campaign audit reconciles all requests. See the campaign budget for the global charge and reservation audit.

Rollout-related budget exposure found at analysis time: **0.068879412 USD**, including any uncertain/reserved charges. This value is an exposure accounting measure, not necessarily final settled billing.

- [All trajectories](figures/rollout_trajectories.png) ([SVG](figures/rollout_trajectories.svg))
- [Outcome and paired-comparison charts](figures/rollout_outcomes.png) ([SVG](figures/rollout_outcomes.svg))
- [Machine-readable summary](rollout_summary.json)
- [Offline regeneration script](analyze_rollouts.py)
