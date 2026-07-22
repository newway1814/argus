---
name: obsidian-vault
description: Search, create, and organize notes in the Obsidian vault. Use when the user asks whether they've already watched/learned/seen something, wants an answer from their notes, or wants notes created or organized; also when another skill (e.g. argus) needs the vault's conventions.
---

# Obsidian Vault

Vault: `<PATH-TO-YOUR-OBSIDIAN-VAULT>`

Plain markdown, zero plugins, no embeddings. Retrieval is Grep + wikilinks (Karpathy LLM-wiki style).

## Structure

| Path | Holds |
|---|---|
| `Digest.md` | Front page. Last 10 processing runs, newest first; older runs live in `Digest Archive.md`. |
| `videos/` | One note per YouTube video (written by the argus skill). |
| `topics/` | MOC index notes, one per discipline (e.g. `AI Agents.md`). A video is linked from every topic it touches. |
| `tools/` | One dossier per tool/project, appended each time a new video mentions it. |
| `videos/_processed.txt` | Ledger of processed video IDs, one per line. |

## Conventions

- `[[wikilinks]]` everywhere; Title Case filenames.
- Video notes are named `YYYY-MM-DD - <Title>.md` (published date).
- Every note carries YAML frontmatter with `tags`; video notes add `type` (tutorial | news | explainer | opinion) and `watch-verdict` (skip | skim | watch).
- Topic MOCs are grouped link lists — `- [[note]] — one-line hook`. Create a new MOC when ≥2 notes share a theme no existing MOC covers; also add the new MOC line to `Welcome.md`.
- Tool dossiers: one line on what it is, official link, then one bullet per video: `- [[video note]] — what it said`.
- **Dossier bar:** a tool earns a page only if it's worth remembering — AI tooling, new or obscure projects, things the user might later half-recall ("some video mentioned a thing that…"). Household names (React, Next.js, Docker, …) stay inline as plain text.
- Wikilinks resolve by filename vault-wide: a name may exist in `topics/` **or** `tools/`, never both.

## Retrieval — "have I watched anything about X?"

1. Expand the query into keyword variants: tool names, synonyms, adjacent terms.
2. Grep `tools/` first (a hit is a full cross-video dossier), then `topics/`, then all of `videos/`.
3. Open the hits; follow wikilinks one hop.
4. Answer from the notes — cite `[[note name]]` and include the deep-linked timestamp when the user may want the video moment itself.

Done when every keyword variant has been grepped and the answer cites specific notes — or you state plainly that nothing in the vault covers it.
