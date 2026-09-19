# Labelled follow-up: full prompt-factorial trajectories

**LABELLED FOLLOW-UP initiated after the original 48 rollout outcomes were observed. The same eight equations and two seeds are reused. This is not an independent confirmation or a fresh holdout; no winning arm is automatically confirmed.**

The six missing prompt combinations were added to the original two random-menu combinations. This gives 128 episodes: eight prompt cells × eight equations × two seeds. The 16 guaranteed-coverage episodes remain separate because they change the menu algorithm. All actions were replayed, exact roots checked, and every solved claim verified as a literal `x = exact_root`.

| Neutral | Structured | Guided | Solved | Mean stop decisions | Median successful decisions | Mean completion-budget score |
|---|---|---|---:|---:|---:|---:|
| 0 | 0 | 0 | 13/16 | 20.25 | 22 | 27.50 |
| 0 | 0 | 1 | 13/16 | 20.31 | 21 | 28.06 |
| 0 | 1 | 0 | 8/16 | 20.38 | 16.0 | 37.00 |
| 0 | 1 | 1 | 4/16 | 20.56 | 15.0 | 45.31 |
| 1 | 0 | 0 | 9/16 | 19.06 | 19 | 35.56 |
| 1 | 0 | 1 | 14/16 | 18.88 | 17.0 | 24.19 |
| 1 | 1 | 0 | 11/16 | 18.94 | 16 | 30.00 |
| 1 | 1 | 1 | 9/16 | 18.69 | 14 | 35.50 |

Stop decisions include failures and do not measure speed to a correct solution. Successful-only counts condition on success. Completion-budget score uses actual decisions for solved episodes and the predeclared common case limit for failures; lower is better. This is a transparent failure penalty, not an imputed continuation.

## Paired factorial main effects

Each effect compares a factor enabled versus disabled, averaged across the other four combinations, then the two repeats, within each equation. Case means receive equal weight. Intervals resample the eight case clusters 20,000 times; they are exploratory, unadjusted for multiple comparisons, and cannot create independence from the reused equations.

| Toggle | Solve-rate difference, percentage points (95% case-bootstrap interval) | Completion-budget-score difference (95% interval) |
|---|---:|---:|
| neutral | +7.81 (-6.25, +26.56) | -3.16 (-9.36, +1.45) |
| structured | -26.56 (-37.50, -15.62) | +8.12 (+3.44, +12.83) |
| guided | -1.56 (-9.38, +7.81) | +0.75 (-2.58, +3.61) |

## Two-factor interactions

**Collection-phase confound:** the original `000` and `111` cells were collected before the other six cells. Their placement on the diagonal can create an apparent two-factor interaction under a common phase offset. These interaction values are descriptive, not identified causal prompt interactions. Main effects cancel only a common additive phase shift. See the [explicit phase-confounding derivation](FACTORIAL_PHASE_CAVEAT.md).

Interactions are differences in differences, averaged over the third factor and repeats. A nonzero result describes differences between the observed cells; collection phase and prompt dependence cannot be separated for these interaction estimates.

| Factors | Solve difference in differences, percentage points | Completion-score difference in differences |
|---|---:|---:|
| neutral_x_structured | +34.38 | -10.50 |
| neutral_x_guided | +21.88 | -7.38 |
| structured_x_guided | -34.38 | +12.31 |

## Limits and interpretation

The original four-template holdout designation is preserved as metadata, but these follow-up results are not a new held-out confirmation: all eight equation trajectories had already been seen before this extension. Arm rankings can generate a hypothesis for genuinely new equations; selecting the best observed arm does not establish that it will be best elsewhere.

All prompt cells use random menus with the same case/seed generator, root-preserving engine, and stopping safeguards. Their first menus match; later menus diverge when controller choices change the state. Eight cases and repeated trajectories do not establish an architectural limitation or a broad-domain conclusion. Neutral wording, structured representation, and added strategy guidance can interact. Guidance adds useful information, and the structure table also changes prompt length.

The separate combined-prompt/coverage policy solved **16/16**. Coverage uses deterministic reference scoring to guarantee a best-scored move is offered, so its success is external algorithmic support rather than an improved model.

Additional logged-decision cost: **$0.14885212**. The unchanged shared campaign budget remains the authoritative global exposure ledger; any uncertain request charges are retained there.

- [All eight prompt cells](figures/factorial_rollout_cells.png) ([SVG](figures/factorial_rollout_cells.svg))
- [Factorial main effects](figures/factorial_rollout_effects.png) ([SVG](figures/factorial_rollout_effects.svg))
- [Machine-readable summary](factorial_rollout_summary.json)
