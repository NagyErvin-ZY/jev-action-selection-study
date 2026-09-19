# Optional fresh API run

Offline reproduction is the default and is sufficient to check the article. No API calls were made while preparing this release.

To deliberately collect new responses to the frozen main-campaign design:

```sh
export OPENROUTER_API_KEY='your-key'
.venv/bin/python rerun.py --execute --output runs/new-main --cap-usd 0.50
```

Set the key in your environment; do not commit it. The example budget may stop before all tasks finish. The workflow contains 3,278 static tasks and 48 complete-run tasks. It reuses the published equations, including the 24 saved pilot states, and is not a new-family confirmation study. The later six-cell follow-up is not included.

The output directory must not already exist. Original evidence is extracted into `frozen-input/`; all new responses and a separate persistent ledger go into `new-results/`. The original archive and published figures are never overwritten. Interrupted runs are retained for inspection; automated resume is not implemented.

The request pins `typesafe/jev-1.13-20260917`, disables fallback through the existing payload and verifies the returned model/provider. If that exact revision is unavailable, the request fails rather than substituting another model. A mismatched successful response halts further reservations; already in-flight requests may still settle. Failed requests can still be billable.

Each attempt reserves 0.002 USD before transmission. Unknown charges retain that reservation. Unexpected per-request charges halt the run; the historical provider price cap remains in requests. The cap controls locally accounted spending under these price and reservation assumptions and does not override provider billing. The recorded main study's prompts were at most 11,461 billed input tokens. Existing time, retry and per-trajectory safeguards are reused.

The optional wrapper adds isolated accounting and strict revision checks around the frozen experiment mechanics. It is tested with fake transport/accounting, not with additional live inference. It deliberately does not use the historical `audit_campaign.py` cost assertions on new data; those assertions describe the published study only.
