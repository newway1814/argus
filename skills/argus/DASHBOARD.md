# Dashboard rebuild

The dashboard is the phone-side face of the vault: one glanceable page, republished to the same private Artifact URL after every run. It aggregates; it never duplicates note bodies — every card deep-links out (YouTube `?t=` links, instagram links).

1. Gather from the vault: `Try Queue.md` (weekly pick + untried count), the `Digest.md` entries since the previous rebuild, every note with `watch-verdict: watch|skim` not yet marked seen, and totals (notes, topics, dossiers; failures noted in recent digests).
2. Write `<vault>/_dashboard.html` with exactly four sections, in order:
   1. **Try Queue** — this week's experiment as a hero card (what it does, setup cost, source link), then the untried count.
   2. **Fresh** — recent digest lines, newest first: title, TL;DR, verdict badge, deep link.
   3. **Awaiting eyeballs** — `watch`/`skim` items with their minute-ranges.
   4. **State of the brain** — counts, trending topics/tools across recent runs, last-drain time, any fetch failures.
   Phone-first: single column, large tap targets, verdict badges color-coded, both themes supported. No search box, no nav, no inbox.
3. Publish: load the `artifact-design` skill first if this session hasn't, then call Artifact with `file_path: <vault>/_dashboard.html`, favicon `👁️`, and `url:` = `dashboard_url` from `config.local.json` so the URL never changes. First publish ever: omit `url`, then store the minted URL into `dashboard_url`.

Done when the Artifact republish succeeds and the URL in config still matches.
