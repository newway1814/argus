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
| `Digest.md` | Front page. Last 10 processing runs, newest first; older runs live in `Digest Archive.md`. Scaffolded as a `# Digest` heading followed by a `---` rule; every new entry is prepended directly below that rule, so the rule must exist before the first run. |
| `videos/` | One note per watched video or reel (written by the argus skill). |
| `topics/` | MOC index notes, one per discipline (e.g. `AI Agents.md`). A video is linked from every topic it touches. |
| `tools/` | One dossier per tool/technique, appended each time a new video mentions it. |
| `videos/_processed.txt` | Ledger of processed items, one `<source>:<id>` identity per line. |
| `_inbox.jsonl` | Durable copy of everything shared to the Telegram bot, written before the Bot API is allowed to forget it. |
| `Try Queue.md` | Workflows saved but not yet tried. One **weekly pick** at top; sections: Untried / Tried / Dismissed. |

## Conventions

- `[[wikilinks]]` everywhere; Title Case filenames.
- Video notes are named `YYYY-MM-DD - <Title>.md` (published date) and carry an `identity` (`<source>:<id>`) in frontmatter — the same string the ledger holds. Neither the name nor the frontmatter is written by hand: the argus skill's `note_writer.py` emits both, and it owns the field list and the `type` / `watch-verdict` enums, so there is one place to change them.
- Every note carries YAML frontmatter with `tags`. Tag with the names of the `topics/` MOCs the note belongs to and nothing else — invented one-off tags are unsearchable, since retrieval here is Grep and wikilinks.
- `try` notes get a line in `Try Queue.md` (Untried section): `- [[note]] — what the workflow does · setup cost`. The weekly pick rotates when older than 7 days: current pick moves back to Untried (or Tried/Dismissed per the user), the oldest Untried item becomes the pick.
- **Mid-task surfacing:** when the user's current work matches a `try` note's workflow, mention it — "you saved a reel about exactly this" — and on their say-so move it to Tried.
- Topic MOCs are grouped link lists — `- [[note]] — one-line hook`. Everything below the preamble is watched material: `## From your videos` for a short list, or descriptive group headings (`## Building & orchestration`, `## Where it's heading`) once a topic has enough notes to sort. Create a new MOC when ≥2 notes share a theme no existing MOC covers; also add the new MOC line to `Welcome.md`.
- **A topic page teaches its own concept.** Above the link list sits a preamble that explains the idea to someone meeting it cold — because a topic the user has watched two videos about *is* a concept they are trying to understand, and a page that only lists links assumes the very knowledge they lack. Shape:

  ```markdown
  > **What it is** — background, not from your videos · sources checked YYYY-MM-DD

  Plain language, with the analogy that makes it click.

  ### How you'll actually meet it
  Where it shows up in practice, in the tools they already use.

  ### A concrete one
  One worked case, tied to a video they watched. Only when there is something
  real to say — a forced example on a thin topic is filler.

  ### Easy to confuse
  Mandatory. The misunderstandings that actually block people; official docs
  never list these, which is why this section is the most valuable one.

  ### If you want the real thing
  Link to the canonical source.

  ## From your videos
  - [[note]] — what it said
  ```

  Background is cited to primary sources and dated, so it can be checked and its age is visible. It is the one part of the vault not derived from something watched — never let it blur into the link list.
- **Write the preamble lazily, never mid-drain.** Add it when the user opens a topic and wants it, asks to be taught something, or asks for a batch. A drain is already paying for frames; a source fetch on top buys nothing at the moment nobody is reading. A topic page with no preamble yet is normal, not a defect.
- **The teaching bar reuses the MOC bar.** ≥2 videos → it is a topic page, so it gets taught. One video → a one-line plain gloss inline in that note, no page; it graduates if it recurs. "Teach me X" promotes anything immediately.
- Tool dossiers: one line on what it is, official link, then one bullet per video: `- [[video note]] — what it said`.
- **Dossier bar:** a page is earned by anything worth remembering by name — tools, techniques, named methods, obscure projects; the things the user might later half-recall ("some video mentioned a thing that…"). AI tooling is the archetype, but a knife-sharpening method or a training protocol qualifies the same way. Household names (React, Docker, olive oil, …) stay inline as plain text.
- Wikilinks resolve by filename vault-wide: a name may exist in `topics/` **or** `tools/`, never both.

## Retrieval — "have I watched anything about X?"

1. Expand the query into keyword variants: tool names, synonyms, adjacent terms.
2. Grep `tools/` first (a hit is a full cross-video dossier), then `topics/`, then all of `videos/`.
3. Open the hits; follow wikilinks one hop.
4. Answer from the notes — cite `[[note name]]` and include the deep-linked timestamp when the user may want the video moment itself.
5. **Keep watched material and background apart.** A topic page's preamble is explanation, not something the user watched; its `## From your videos` bullets are. Answering "have I watched anything about X?" from a preamble would tell them they've seen something they haven't. Say which is which — "you haven't watched anything on this, but the topic page explains it" is a good answer.

Done when every keyword variant has been grepped and the answer cites specific notes — or you state plainly that nothing in the vault covers it.
