# Follow-up timing caveat for the prompt-factorial trajectories

**The six added prompt combinations were collected after the original `000` and `111` combinations. These eight arms are therefore not a contemporaneously randomized full-factorial experiment.** The extension is useful exploratory evidence on the same eight equations, but its two-factor interactions have a specific collection-phase confound.

For any pair of prompt factors, the `00` cell contains one original-phase arm and one follow-up arm after averaging over the third factor. The `11` cell likewise contains one original-phase arm and one follow-up arm. The `01` and `10` cells contain only follow-up arms.

If every original-phase result had an additive offset of δ relative to the follow-up phase, independent of prompt and case, the usual two-factor difference in differences would acquire an artificial interaction of δ:

`interaction = mean(11) − mean(01) − mean(10) + mean(00)`

`phase contribution = δ/2 − 0 − 0 + δ/2 = δ`

For example, a shared difference caused by model service conditions or unmeasured collection timing could appear as a prompt-factor interaction even if the factors did not interact. The current dataset cannot separate these explanations. A case-cluster bootstrap quantifies variation across the observed cases; it does not remove a phase confound.

The marginal main-effect comparisons have a narrower protection: each enabled/disabled side contains one original arm and three follow-up arms, so a **common additive phase offset cancels**. This does not establish immunity to a phase effect that varies with the prompt, case, trajectory state, or response distribution. The same reused equations and observed-result motivation also remain limitations.

Accordingly:

- Treat two-factor interaction values as descriptive patterns, **not identified causal interactions** between prompt components.
- Treat main effects as exploratory paired averages, with the explicit qualification that only a common additive phase shift cancels.
- Do not interpret an arm selected as best in this follow-up as independently confirmed.
- A clean future interaction test would rerun all eight arms with randomized interleaving on genuinely new equations. No such additional paid run was performed for this addendum.

This note is an offline interpretation addendum. It changes no frozen protocol, model request, outcome, or budget entry.
