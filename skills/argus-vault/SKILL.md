---
name: argus-vault
description: Search and organize the Argus watch-vault — notes filed from watched YouTube videos and Instagram reels. Use when the user asks whether they've watched/seen something about a topic, wants an answer from their watch notes, or when the argus skill needs the vault's conventions. Not for the user's other Obsidian vaults or personal notes.
---

# Argus Vault

Vault: the `vault_path` in `~/.claude/argus.config.json` (missing → the argus skill's SETUP.md first-run flow creates it). This skill owns only the Argus watch-vault — never apply its conventions to the user's other vaults or notes.

Plain markdown, zero plugins, no embeddings. Retrieval is Grep + wikilinks (Karpathy LLM-wiki style).

## Structure

| Path | Holds |
|---|---|
| `Digest.md` | Front page. Last 10 processing runs, newest first; older runs live in `Digest Archive.md`. |
| `videos/` | One note per watched video or reel (written by the argus skill). |
| `topics/` | MOC index notes, one per discipline (e.g. `AI Agents.md`). A video is linked from every topic it touches. |
| `tools/` | One dossier per tool/technique, appended each time a new video mentions it. |
| `videos/_processed.txt` | Ledger of processed video IDs, one per line. |
| `Try Queue.md` | Workflows saved but not yet tried. One **weekly pick** at top; sections: Untried / Tried / Dismissed. |

## Conventions

- `[[wikilinks]]` everywhere; Title Case filenames.
- Video notes are named `YYYY-MM-DD - <Title>.md` (published date).
- Every note carries YAML frontmatter with `tags`; video notes add `type` (tutorial | news | explainer | opinion | workflow) and `watch-verdict` (skip | skim | watch | try).
- `try` notes get a line in `Try Queue.md` (Untried section): `- [[note]] — what the workflow does · setup cost`. The weekly pick rotates when older than 7 days: current pick moves back to Untried (or Tried/Dismissed per the user), the oldest Untried item becomes the pick.
- **Mid-task surfacing:** when the user's current work matches a `try` note's workflow, mention it — "you saved a reel about exactly this" — and on their say-so move it to Tried.
- Topic MOCs are grouped link lists — `- [[note]] — one-line hook`. Create a new MOC when ≥2 notes share a theme no existing MOC covers; also add the new MOC line to `Welcome.md`.
- Tool dossiers: one line on what it is, official link, then one bullet per video: `- [[video note]] — what it said`.
- **Dossier bar:** a page is earned by anything worth remembering by name — tools, techniques, named methods, obscure projects; the things the user might later half-recall ("some video mentioned a thing that…"). AI tooling is the archetype, but a knife-sharpening method or a training protocol qualifies the same way. Household names (React, Docker, olive oil, …) stay inline as plain text.
- Wikilinks resolve by filename vault-wide: a name may exist in `topics/` **or** `tools/`, never both.

## Retrieval — "have I watched anything about X?"

1. Expand the query into keyword variants: tool names, synonyms, adjacent terms.
2. Grep `tools/` first (a hit is a full cross-video dossier), then `topics/`, then all of `videos/`.
3. Open the hits; follow wikilinks one hop.
4. Answer from the notes — cite `[[note name]]` and include the deep-linked timestamp when the user may want the video moment itself.

Done when every keyword variant has been grepped and the answer cites specific notes — or you state plainly that nothing in the vault covers it.
