# Using Jev to choose the next action

A small study of Jev 1.13 selecting operations in an exact-arithmetic algebra controller. The engine performs arithmetic; Jev chooses an action. Conducted on 19 September 2026.

The pilot scores every offered algebra action counterfactually, then compares its reference-policy completion cost with Jev’s full probability distribution. Across 24 runs on three equations, mean probability quality was **0.845** and pairwise alignment **0.705**, with equal run weights. The figures follow those preferences through progress and cutoffs.

The original prompt solved **13/16** runs. Combined prompt changes solved **9/16**. Guaranteeing a best reference-scored action in each menu, with the same combined prompt, produced **16/16**. That last condition includes external solver assistance. Each condition has eight equations and two seeds.

[Read the field note](https://www.nagyervin.com/writing/jev-action-selection) · [Technical appendix](docs/APPENDIX.md) · [Claim-to-evidence index](docs/CLAIMS.md)

## Reproduce without model calls

Python 3.12 was used. From a clean checkout:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python reproduce.py
```

Installing dependencies needs a package source. Reproduction itself needs neither network access nor an API key. Analysis subprocesses have sockets disabled. Allow a few minutes and approximately 400 MB for extracted evidence and plots.

The command checks the public archive, reconstructs all 2,747 main/follow-up trajectory decisions, recomputes static scores, and rebuilds reports and figures in `reproduced/`. It refuses to overwrite existing output; choose another location with `--output new-directory`.

Start with `reproduced/field-note-figures/` for the revised article figures and their plotted data, and `reproduced/headlines.json` for campaign counts. Detailed figures and rebuilt reports are in its `jev-hypotheses/` directory. The repository appendix remains the authoritative interpretation: historical generated reports retain the language used at the time and must be read with the documented corrections.

## What is included

- `evidence.zip`: public snapshot of the pilot, frozen main campaign and later follow-up. Exact requests and numerical model responses are included.
- `study/`: byte-identical source mirrors for browsing. Reproduction runs the same sources extracted from the archive.
- `public-manifest.json`: original and public hashes, with explicit markers for redacted files.
- `docs/`: methods, corrections, complete treatment reports and figures.
- `tools/build_field_note_figures.py`: replay all 689 pilot decisions and rebuild distribution figures with checked counterfactual costs.
- `tools/verify_results.py`: independent reconstruction of requests, actions and stopping conditions, plus article assertions.

The full study used **6,025 requests**, costing **0.540718080 USD**; including the pilot, **0.608268318 USD**. No model calls were made to prepare this publication. These are recorded costs, not current-price promises.

## Optional new calls

`rerun.py` is a separate opt-in workflow. It repeats the frozen main-campaign design into a new directory, including its saved pilot diagnostic states. It does not create a new independent set of equation families or repeat the later six-cell follow-up. See [RERUN.md](docs/RERUN.md). It requires an explicit spending cap and execution flag. Merely installing or reproducing never calls a model.

## Scope and reuse

This is an exploratory study across eight new equation templates. It does not rank Jev against other models, establish a general algebra capability, or test a research agent. The later prompt follow-up has a collection-phase confound described in the appendix.

Original code: [MIT](LICENSE). Original documentation and experiment-data contributions: [CC BY 4.0](LICENSE-DATA.md), to the extent those rights exist. Third-party rights are excluded; see [NOTICES.md](NOTICES.md). AI assistance is disclosed in the appendix.
