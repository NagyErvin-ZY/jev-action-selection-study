# Public snapshot and corrections

The archive is a publication derivative of the local experiment, not an unmodified dump. `public-manifest.json` contains SHA-256 hashes for each original file and each released file. `changed` identifies byte differences. `redactions.json` records the removed field categories by file without disclosing the removed values.

Provider-generated `gen-dec-...` identifiers were removed from response objects, including duplicate response copies in attempt records. Local filesystem references were replaced with `[LOCAL_PATH_REDACTED]`. Exact requests and numerical answers remain unchanged. No credentials are included.

Disposable progress checkpoints, logs, caches and obsolete packaging manifests are omitted. The complete final trajectories and transport-attempt evidence remain included. Original and public hash values are evidence of the documented transformation; the original private files are not required to reproduce the released measurements.

Python source files are unchanged. Their browseable copies under `study/` must match the archived copies. Protocol source and dataset hashes that define experiment mechanics remain checked during reproduction. Redacted provenance fields are not presented as original bytes. Figure files may differ byte-for-byte after regeneration because of rendering metadata; their underlying numbers are checked.

The public appendix corrects two earlier interpretations: outer-expansion difficulty depends strongly on the reference policy, and saved-state uncertainty must cluster over three equations. It also explicitly documents the later prompt follow-up's phase confound. Archived reports are historical outputs. Rebuilding a historical report does not erase the interpretive corrections in the main appendix.

No GPQA questions, unrelated conversations, model weights or provider website content are included. All research inputs here are constructed equations and prompts from this experiment.
