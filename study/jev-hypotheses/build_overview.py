"""Offline overview; reads completed, audited results and never calls a model."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    audit=json.loads((ROOT/'audit.json').read_text())
    full=json.loads((ROOT/'factorial_rollout_summary.json').read_text())
    assert audit['passed'] and audit['followup_rollout_records']==96
    rows=[]
    names={
        'n0_s0_g0':'Original prompt', 'n0_s0_g1':'Guidance only',
        'n0_s1_g0':'Structure table only', 'n0_s1_g1':'Structure + guidance',
        'n1_s0_g0':'Neutral wording only', 'n1_s0_g1':'Neutral + guidance',
        'n1_s1_g0':'Neutral + structure', 'n1_s1_g1':'All three changes',
    }
    for key,name in names.items():
        a=full['arms'][key]
        rows.append(f"| {name} | {a['solved']}/16 | {a['mean_completion_budget_score']:.2f} |")
    table='\n'.join(rows)
    text=f'''# Jev: controlled algebra-controller investigation

**Completed 19 September 2026. All listed experimental arms finished.** This is a behavioural investigation of `typesafe/jev-1.13-20260917`, served by TypeSafe through OpenRouter. Jev chooses an operation; a deterministic exact-arithmetic engine executes it. These experiments test decision selection, not the model's ability to perform arithmetic unaided.

The strongest practical finding is that **the controller's menu design matters, and better local probability scores do not guarantee better completed trajectories**. Fraction-heavy states and option ordering also expose measurable weaknesses. Some apparent mistakes disappear when the reference solver changes, so evaluator robustness is essential.

## Scale, cost and safeguards

- **3,278 static requests**, covering 152 fixed states/menus: 128 newly generated states from eight templates, plus 24 diagnostic states from the previous three equations.
- **144 complete trajectory attempts**: eight prompt variants × eight equations × two seeds = 128, plus 16 runs with externally supported menu coverage. The six additional prompt variants were a labelled follow-up after observing the initial 48 runs.
- **{audit['requests']:,} new API requests / {audit['attempts']:,} attempts**, all reconciled with saved responses and the persistent budget ledger. HTTP outcomes: {audit['http_statuses']}. Unsettled or unknown charges: {audit['unsettled_or_unknown_costs']}.
- New investigation cost: **${float(audit['new_cost_usd']):.6f}**, approximately **£{audit['new_cost_gbp_estimate']:.3f}**.
- Including the original algebra experiment: **${float(audit['combined_accounted_exposure_usd']):.6f}**, approximately **£{audit['combined_cost_gbp_estimate']:.3f}**. The shared cap was the stricter **$2 USD**, below the requested £2 at the recorded exchange rate (£1 = ${audit['fx_gbp_usd']}). GBP is a conversion estimate, not a card statement.
- Guards bounded consecutive/total rerolls, repeated states, stagnation, premature completion, decisions, elapsed time, prompt size, retries and global spend. Failures remain in denominators. Every trajectory was replayed with exact solution checks.

## Hypothesis results

| Hypothesis | Result | Evidence and scope |
|---|---|---|
| Fraction-heavy expressions are harder | Supported for this constructed regime | Baseline probability quality fell by **0.148–0.182** across all three evaluators. Both numeric regimes had 89.06% of menus containing an improving move. This does not isolate fractions from all induced root/menu/scale changes. |
| Deep nesting is the principal weakness | Mixed | Deep-minus-shallow was −0.068/−0.077 for two evaluators and +0.006 for cleanup-first. It is not a robust universal depth ceiling. |
| Wider expressions or larger coefficients reliably hurt | Not established | No consistent detrimental effect across evaluators and templates. |
| Explicit strategy guidance improves action distributions | Supported locally | Full-factorial guidance effects were **+0.0451**, **+0.0316**, **+0.0244** quality points across reference/shallow/cleanup evaluators; all exploratory intervals were above zero. |
| Neutral descriptions reliably help | Not established | The overall local effect was small or inconsistent; the full-run marginal effect was also uncertain. |
| A lossless structure table makes the agent more reliable | Evidence against this representation | Replacing ordinary equation text with our node-ID table reduced the full-run solve rate by **26.56 percentage points** on average (exploratory interval −37.50 to −15.63). Seven of eight equations worsened and one tied. The static local metric did not reveal this substantial trajectory loss. |
| Combining prompt improvements guarantees better agents | Contradicted in the first frozen trajectory comparison | Original random-menu prompt solved **13/16**; combined changes solved **9/16**, despite favourable local metrics. |
| Missing useful choices contribute to failure | Supported as a controller-level explanation | Combined prompt with random menus solved **9/16**; guaranteeing a best reference-scored move in each menu solved **16/16**. This is external algorithmic help, not improved model intelligence. |
| Option order changes behaviour | Supported on the tested states | Reversing options produced semantic distribution TV **0.1365**, versus **0.0327** observed identical-repeat TV on 16 fresh side-test states. Mean cross-repeat choice flips: **18.75%**. |
| Random-word labels are the main issue | Smaller effect than order here | Random words alone: TV **0.0491**, choice flips **6.25%**. Words plus reversal: **21.875%** flips. Labels were mapped back to the actual operations before comparison. |
| Extra context/history is the main bottleneck | Not established in this range | Fresh-state padding quality intervals crossed zero through **11,461 billed input tokens**. Removing history from saved states also gave inconclusive quality effects. This does not test the full context window or realistic long histories. |
| High reported probability means the chosen move is correct | Unsupported | Confident reference-suboptimal choices remain. These distributions are action preferences, not calibrated probabilities of eventual success. |
| All apparent mistakes are evaluator artefacts | Contradicted | Exhaustive bounded search proved **5** selected multiplication moves suboptimal in a targeted eight-state subset; one other reference flag was a false positive and two remained unresolved. |
| We can identify the internal architectural cause | Not identified | Controlled input interventions reveal operational sensitivity, not unique internal mechanisms. |

Local probability quality is normalized to 0–1 within a fixed offered menu: 1 assigns all conditional algebra-action mass to the best reference-scored actions, and 0 assigns it to the worst. Reroll and completion are excluded and the remaining probabilities renormalized. This is not accuracy, a true target probability density, or universal shortest-path distance. Menu interventions are evaluated using regret relative to the full legal action pool to avoid moving the scoring baseline.

## Complete equation outcomes for every prompt combination

| Prompt | Solved | Mean completion-budget score, lower better |
|---|---:|---:|
{table}
| All three + guaranteed reference-best menu coverage | 16/16 | 14.62 |

Each random-menu arm contains eight equations and two repeats. Completion-budget score equals actual decisions for successful runs and the same predeclared case decision cap for unsuccessful runs. It is an explicit failure penalty, not a prediction of how long a failed run would take. The accompanying reports also give raw stopping counts, success-only counts, cutoffs, and exact trajectories.

**Collection-phase limitation:** original and all-three prompt cells were collected first; the other six cells were collected later on the same equations. The follow-up is exploratory. Its two-factor interactions are confounded with collection phase; they must not be interpreted as isolated causal prompt interactions. A common additive phase effect cancels from marginal main effects, but more complex drift need not. See [the full derivation](FACTORIAL_PHASE_CAVEAT.md). The best observed arm is not independently confirmed.

![All prompt combinations](figures/factorial_rollout_cells.png)

![Initial frozen rollout comparison](figures/rollout_outcomes.png)

## Important correction to the earlier diagnosis

The earlier outer-expansion failure claim was too strong. Of 37 selected outer-expansion moves, **34** had a better offered move under the original reference strategy, versus **9** under shallow-first and **21** under cleanup-first. That is evaluator-sensitive evidence, not a demonstrated general incapacity for outer expansion.

Multiplication choices were more consistently questionable: **28/49**, **27/49**, and **27/49** had a better offered alternative under the three policies. Stronger search evidence comes from a deliberately selected tractable subset, not a prevalence estimate: five of eight flagged multiplication decisions were proven suboptimal, one was proven optimal, and two were unresolved under bounded search.

For example, at `((1)*x + -7/3) = 0`, multiplying by 3 leaves at least three moves under the permitted action system. Simplifying `1*x` leaves exactly one. This proves at least two avoidable moves. All three reference policies share the same exact algebra engine; agreement among them is not independent validation of that engine.

## What this means for using Jev

The evidence favours a constrained decision selector inside a deterministic controller: generate legal actions, provide clear mechanical descriptions, maintain external progress and loop guards, and verify outcomes. Menu quality is part of the system being evaluated. Where a cheap deterministic method can already rank actions perfectly, Jev may add little for this algebra task; the experiment is a controlled probe of its selection behaviour.

For agentic search, swarm routing or coding, the corresponding hypothesis is that it may work well when the surrounding system supplies a small, useful set of verifiable next actions. **Those domains were not tested here**, and their outcomes do not follow from these algebra results. Nor does changing its inputs demonstrate training overfitting.

## Statistical and reproducibility limits

Fresh intervals resample **eight equation templates**, not 128 independent families. Saved-state intervals use **three original equations** as clusters, with equal equation weights; earlier episode-cluster summaries have been superseded. There are many exploratory contrasts, and reported 95% intervals are pointwise, without multiplicity correction. Zero observed repeat-choice flips in 16 fresh states does not prove zero underlying variability; provider caching is unknown.

Structural factors change the legal action pool, prompt length, score range, and sometimes constructed roots as well as the named structural property. Strategy guidance adds information. Each structural state has one sampled menu. The engine covers single-variable linear equations with exact rational arithmetic and a defined action grammar; this is not evidence about all algebra or arbitrary planning.

Frozen source/request hashes, all probabilities, counterfactual scores, raw responses, charges and cutoffs are retained. The audit recomputes every static score under all three policies, checks protocol hashes and reconciles every budget entry. All 2,747 trajectory decisions additionally had independent reconstruction of menu-to-choice mappings. For the 1,890 follow-up decisions, the complete requests, histories, guard counters, stopping priorities and timing were also reconstructed exactly. All 144 trajectories were replayed for root preservation and valid completion.

## Files

- [Static results, uncertainty and all hypothesis contrasts](STATIC_REPORT.md)
- [Original 48 trajectory results](ROLLOUT_REPORT.md)
- [All eight prompt combinations](FACTORIAL_ROLLOUT_REPORT.md)
- [Collection-phase caveat](FACTORIAL_PHASE_CAVEAT.md)
- [Evaluator audit and bounded shortest-path proofs](ORACLE_REPORT.md)
- [Accounting and integrity audit](audit.json)
- [Independent follow-up request, action and cutoff audit](followup_mapping_audit.json)
- [Every original-comparison trajectory](figures/rollout_trajectories.png)
- [Machine-readable static summary](static_summary.json)
- [Machine-readable full-factorial trajectories](factorial_rollout_summary.json)
- Python: `analyze_static.py`, `analyze_rollouts.py`, `factorial_rollouts.py --analyze`, `oracle_audit.py`, `audit_campaign.py` and `build_overview.py`. Offline analysis does not require an API key. Only explicit execution flags perform paid calls.

The archive includes both this investigation and the original `jev-algebra` directory because the exact engine and original diagnostic data are dependencies. Earlier original reports are historical; this report and the oracle audit supersede their overstrong outer-expansion interpretation.
'''
    (ROOT/'REPORT.md').write_text(text)
    (ROOT/'README.md').write_text('# Jev hypothesis experiment\n\nStart with [REPORT.md](REPORT.md). All arms are complete; no model calls remain running.\n\nThe archive preserves sibling `jev-algebra` and `jev-hypotheses` directories. Install the versions in `environment.json` or the sibling original requirements file. Run analyses from their directory; imports resolve the sibling engine automatically.\n\nDo not rerun `--execute` merely to view results. Frozen raw data and offline plot scripts are included.\n')

if __name__=='__main__': main()
