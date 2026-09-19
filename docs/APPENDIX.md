# Technical appendix: Jev action selection

Version 1.0.0. Study date: 19 September 2026. This appendix distinguishes observations from possible applications. It is a practitioner experiment, not a peer-reviewed paper.

## 1. Scope and sequence

The model selected operations in single-variable linear equations with exact rational arithmetic. Software generated legal actions and executed their transformations. Literal completion meant `x = exact numeric root`. Jev was not asked to calculate replacements or generate algebra steps as free text.

Three stages must remain distinct:

| Stage | Cases and design | Purpose |
|---|---|---|
| Pilot | Three fixed equations, eight Jev runs per equation | Develop trajectory and probability diagnostics |
| Frozen main campaign | 128 fresh states from eight templates, 24 saved pilot states; eight prompt combinations, two repeats; side tests; 48 complete runs | Compare controlled prompts and menus; inspect completed trajectories |
| Later follow-up | Six remaining prompt combinations on the same eight rollout equations, two seeds | Explore why the combined prompt completed fewer runs |

The 128 fresh static states are eight templates crossed with a full 2×2×2×2 design: nesting, branch width, coefficient magnitude and integer/rational regime. These are 128 states, not 128 independent equation families. Each has one sampled baseline menu shared across prompt treatments. Four templates were designated diagnostic and four held out before the main campaign; no claim of a fresh holdout applies to the later follow-up.

The main campaign contains 2,432 core static calls, 240 menu calls, 240 label calls and 366 history/padding calls: 3,278 fixed-state decisions. Initial rollouts contain 857 decisions and the follow-up contains 1,890: 6,025 calls in total. All returned HTTP 200; these transport successes are not task successes.

Exact input states, generators and task lists are under the two sibling directories in the archive. The pilot remains included because it supplies diagnostic states and evaluator-audit examples. Its random-policy comparison belongs to those pilot equations and is not a matched control for the new campaign.

## 2. Model, prompts and actions

Requests used `typesafe/jev-1.13` through OpenRouter's decisions endpoint. Every recorded response resolved to **`typesafe/jev-1.13-20260917`**, provider **TypeSafe**. Provider fallback was disabled. This report describes that observed version. Current service availability is not required for offline reproduction.

The action pool permits local algebra transformations, including evaluating products, expanding a product over a sum, removing redundant grouping, combining terms, adding a constant or variable term to both sides, multiplying both sides by a nonzero value, swapping sides and declaring completion. The engine grammar determines which actions exist at each state. No offered action directly invokes the complete solver.

Menus contain ten sampled pool actions plus reroll. A premature completion declaration may occupy one of the ten slots. Reroll leaves the equation unchanged and consumes a decision. Completion is also detected automatically after a transformation.

The original prompt already contains strategy advice and action explanations. The three experimental toggles are:

- **Neutral:** delete generic benefit clauses from descriptions, retaining mechanics and exact local replacements. This removes information as well as changing tone.
- **Structured:** replace ordinary equation text with a lossless node-ID table and unambiguous target references. It changes presentation and prompt length.
- **Guided:** add generic precedence/dependency advice beyond the original guide. It is not a comparison of guidance with no guidance.

See `study/jev-hypotheses/prompt_arms.py` and the archived requests for exact wording. The main article's example is `rollout__rollout_00_nested_chain__original_random__r0__s001.json`. Its displayed equation is `(6)*((((2)*(x) + 5))) = 65`. The shorter article notation suppresses the extra grouping node; the source request and action that removes it remain available.

## 3. Progress and probability scores

For state s and offered algebra action a, execute the action on a copy and compute d(a) = D(T(s,a)). D is the number of remaining operations under a deterministic reference policy. This **reference-policy completion cost is not generally a shortest-path distance**.

Remove reroll and completion declarations. Normalize the remaining reported probability mass to obtain p(a). Keep the excluded mass separately. The reports preserve the provider's original rounded probabilities as well as normalized quantities.

```text
best = min_a d(a)
worst = max_a d(a)
expected_regret = sum_a p(a) * (d(a) - best)
probability_quality = 1 - expected_regret / (worst - best)
```

Zero algebra mass and equal-quality menus have undefined normalized quality. They are counted and excluded, not assigned zero. Quality is within-menu and can be affected by extreme distractors. For comparisons that change the menu, expected regret is also measured relative to the best action in the full legal action pool.

Pairwise alignment considers unequal-cost pairs. It awards 1 when the better action has higher probability, 0 when lower, and 0.5 for a probability tie; it weights each pair by its cost gap. This ranks preferences and does not establish calibration against a true probability distribution of success. Two near-zero-probability alternatives can affect alignment while hardly affecting expected regret.

Trajectory plots show D(s_t)/D(s_0), with zero marking completion, and stop at observed termination. The pilot also records cumulative changes and best-so-far progress. A temporary increase in reference cost can be valid algebra and useful under a different strategy.

## 4. Complete-run outcomes

Each initial policy was fixed before inference and used the same eight equations and two seeds:

| Policy | Solved | Mean completion-budget score |
|---|---:|---:|
| Original prompt, random menus | 13/16 | 27.50 |
| Combined changes, random menus | 9/16 | 35.50 |
| Combined changes, reference-best move covered | 16/16 | 14.625 |

The completion-budget score is actual decisions for solved runs and the common predeclared case limit for failures. It is a transparent penalty, not a guess at the unfinished trajectory. Successful-only timings condition on success; time-to-cutoff is not time-to-solution. Completion curves retain every episode in the denominator.

Coverage guarantees a best action under the original reference policy, not a proven globally optimal action. It changes the menu generator and uses an external solver. The exact engine can already solve these constructed equations deterministically; this is a controlled probe of action selection, not a claim of advantage over ordinary algebra software.

Seeds couple menus while the state and menu-generation process remain identical. After different choices change the state, later menus may differ. Repeated seeds do not make divergent trajectories identical experiments at every later step.

[Initial rollout report](ROLLOUT_REPORT.md) · [All trajectories](figures/rollout_trajectories.png)

## 5. Full prompt follow-up

| Neutral | Structured | Additional guidance | Solved |
|---:|---:|---:|---:|
| 0 | 0 | 0 | 13/16 |
| 0 | 0 | 1 | 13/16 |
| 0 | 1 | 0 | 8/16 |
| 0 | 1 | 1 | 4/16 |
| 1 | 0 | 0 | 9/16 |
| 1 | 0 | 1 | 14/16 |
| 1 | 1 | 0 | 11/16 |
| 1 | 1 | 1 | 9/16 |

The structured-representation marginal difference is −26.5625 percentage points (exploratory eight-case bootstrap interval −37.50 to −15.625). Seven case effects were negative and one was zero. The best observed prompt cell is not independently confirmed.

**Collection-phase confound:** cells 000 and 111 were collected first, the other six later. In any two-factor difference-in-differences, the earlier cells occupy the diagonal. A common additive phase offset can therefore mimic an interaction. That common offset cancels from marginal main effects, but prompt-dependent or case-dependent drift need not cancel. Resampling cases does not remove this confound. The data cannot identify all observed interactions as causal effects of the prompt components.

[Follow-up report](FACTORIAL_ROLLOUT_REPORT.md) · [Full derivation](FACTORIAL_PHASE_CAVEAT.md)

## 6. Other interventions and uncertainty

Static effects average repeats within a state and states within an equation family, with equal family weights. Fresh intervals resample eight templates; saved-state intervals resample only three original equations. Earlier episode-weighted saved summaries were corrected before this release. The 15 source episodes do not supply 15 independent problems.

Additional guidance improved local quality across all three reference policies: +0.0451, +0.0316 and +0.0244. The combined prompt's local effect was evaluator-dependent. Static counterfactual states and complete trajectories are separate evaluations; these results do not estimate a universal correlation between local quality and eventual success.

The rational regime's baseline quality disadvantage was approximately 0.148–0.182 across evaluators. Both integer and rational groups had 89.06% of menus containing a reference-improving action, but other menu content, score-range and constructed-root differences remain. Depth also changes expression size and horizon; width has template-dependent meaning. These comparisons do not isolate an internal mechanism.

Label tests use 40 side states, including 16 fresh states. Random labels are drawn from a 100-word pool. Reversal reorders the ten pool choices while reroll remains last. Comparisons map every label, including completion and reroll, to its exact semantic action. Each treatment averages all four baseline-versus-treatment repeat pairs; these pairs are dependent.

On the fresh side states, reversal gave mean choice flips 18.75%, random words 6.25%, and both 21.875%. Semantic total variation was approximately 0.1365, 0.0491 and 0.1348 respectively. Identical repeats had TV 0.0327 and zero observed choice flips in 16 states. Zero events in that sample does not establish zero variability; provider caching is unknown.

History removal applies only where saved history exists. Padding inserted 2,000 or 6,000 words at the front or end. Fresh quality intervals crossed zero in these padding conditions. Maximum billed input length was 11,461 tokens. This tests particular irrelevant content and placement, not all long-context use or the model's full context limit.

Intervals are exploratory, pointwise and not multiplicity-adjusted. Reported families and treatments are retained regardless of sign. [Complete static report](STATIC_REPORT.md) includes every condition and the omitted/undefined-score counts.

## 7. Evaluator correction and bounded search

Under the original policy, 34/37 selected outer expansions had a better offered alternative. The count was 9/37 under shallow-first and 21/37 under cleanup-first. The earlier broad outer-expansion diagnosis was therefore too strong.

Multiplication counts were more stable: 28/49, 27/49 and 27/49. The three policies share the same exact engine; this agreement is not independent engine validation.

For stronger evidence, bounded breadth-first search examined eight reference-flagged multiplication states selected for tractability near completion. Across 76 offered actions, 55 searches produced exact distances and 21 were node-censored. Five chosen actions were proven suboptimal, one reference flag was proven optimal, and two remained unresolved. This targeted selection cannot estimate the overall prevalence of mistakes.

Search enumerates every engine-generated action, deduplicating exact ordered expression tuples. Exact claims require discovering a goal; capped searches retain explicit lower bounds. At `((1)*x + -7/3) = 0`, multiplying by 3 leaves at least three moves; an offered simplification of `1*x` leaves exactly one. The proof is relative to the engine's defined action grammar.

[Evaluator report and search methodology](ORACLE_REPORT.md)

## 8. Guards, accounting and provenance

Main/follow-up runs enforce three consecutive rerolls, eight total rerolls, three visits to a state, and two premature completion declarations as cutoffs. The decision limit is min(120, max(24, 4D_initial + 12)); stagnation limit is min(30, max(12, D_initial)). Each run also has a 600-second limit. Transport bounds requests, retries and aggregate time; the shared ledger reserves each attempt before sending and retains uncertain charges.

Recorded study cost is 0.540718080 USD; including the pilot it is 0.608268318 USD. The study used a stricter 2 USD combined cap for the user's 2 GBP budget. At the recorded 19 September conversion of 1 GBP = 1.337339 USD, these are approximately 0.404 GBP and 0.455 GBP. These are conversion estimates, not card statements. All 6,025 study attempts settled; none required a retry.

All 144 main/follow-up trajectories were replayed and their exact roots checked. The independent public verification script regenerates each complete request from the seed and history, maps the raw choice to the action and recomputes stopping conditions. Static scoring is recalculated under all three reference policies. Source hashes are checked before analysis. Programmatic checks can share assumptions with the engine; they are not a claim of error-free science.

**AI assistance:** Codex assisted with implementation, experimental orchestration, analysis and writing. Separate agent passes reviewed evaluator logic and reconstructed requests and cutoffs. These were agent reviews, not independent external scientific reviews. The published scripts and evidence allow readers to inspect the work without relying on those reviews.

The public archive removes provider generation identifiers and local filesystem references. It retains exact scientific prompts, action labels, probabilities, model/provider names, timestamps and charges. [PUBLICATION.md](PUBLICATION.md) explains the original/public hash distinction and omissions. Licensing scope and provider-material treatment are documented in [NOTICES.md](../NOTICES.md).

## 9. Applications remain hypotheses

Bounded research navigation and coding-tool selection are plausible next experiments because their actions can be constrained and outcomes inspected. Source evaluation, research sufficiency and safe stopping were not tested. This dataset does not establish an internal architectural cause, a comparative model ranking or a calibrated success predictor.
