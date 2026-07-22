# Argus 👁️

**The hundred-eyed YouTube watcher.** A pair of [Claude Code](https://claude.com/claude-code) skills that *watch* YouTube videos for you — transcript **and** on-screen frames — and file what they teach into an Obsidian vault you can query forever.

Named after Argus Panoptes, the watchman of Greek myth whose hundred eyes never all slept at once.

## The problem

Staying current with AI means watching YouTube: tutorials, workflow demos, news breakdowns. Forty videos a month is ~13 hours of watching. Realistically you watch a handful, feel guilty about the rest, and three months later you can't remember which video showed the exact config you now desperately need.

Summarizer tools read the transcript and stop there — but in tutorials the payload is *on the screen*: the command typed, the config pasted, the menu clicked. The speaker just says "then you paste this in." The transcript never contains *this*.

## What Argus does

You save interesting videos to one unlisted YouTube playlist (two taps — that's your entire manual workload). Then, in Claude Code:

```
/argus queue
```

For every video, Argus:

1. **Tier 1 — reads the transcript** (yt-dlp captions, seconds, no download). Talking-head news resolves here.
2. **Tier 2 — watches the frames.** For tutorials/demos, or whenever the transcript points at the screen ("as you can see…"), it downloads the video, extracts scene-change frames with ffmpeg, and reads each frame *aligned with the words spoken at that timestamp*. Frame + speech = what is actually happening.
3. **Writes a note built for retrieval, not summary:**
   - a 3-sentence TL;DR
   - a **runbook** — numbered steps with the *exact* commands, config, and UI paths quoted from the frames, reproducible without ever watching
   - **prerequisites** and **outdated flags** (AI tutorials rot in weeks — Argus says so)
   - deep-linked timestamps (`?t=862`) so "pull up the video" means landing at 14:22, not scrubbing from 0:00
   - a **watch-verdict**: `skip` / `skim` / `watch`, with the exact minute ranges worth your eyeballs
4. **Cross-links everything**: topic index notes (MOCs) so one video lives in every discipline it touches, and per-tool **dossier pages** that automatically accumulate what every video ever said about LangGraph, Firecrawl, whatever.
5. **Prepends a digest** to the vault's front page: one line per video, newest first.

## The payoff — retrieval

Weeks later you hit a wall and ask, in any Claude Code session:

> "have I watched anything about MCP tool permissions?"

The `obsidian-vault` skill greps the vault — tool dossiers first, then topics, then videos — and answers **from your notes**, citing the exact note and timestamp. No embeddings, no vector database, no RAG pipeline: plain markdown, wikilinks, and text search (the [Karpathy LLM-wiki](https://github.com/green-dalii/obsidian-llm-wiki) philosophy). At personal scale, a well-linked folder of text beats a vector store on every axis — and any agent can read it.

## The vision

Your past scrolling becomes a memory you can query. YouTube stops being a 13-hour backlog and becomes:

- **40 one-line digests** you read in two minutes,
- **~40 minutes of flagged watching** instead of 13 hours (`watch` verdicts are rare and precise),
- and a **second brain that compounds**: video #40 about a tool lands on a dossier page that already remembers what videos #12 and #27 said about it.

The system is honest about what it is: a *reference system with a triage layer*, not a magic learning machine. The agent watches everything; you learn at the moment of need — which is when learning sticks anyway.

## Setup

**Requirements:** [Claude Code](https://claude.com/claude-code), Python + `pip install yt-dlp`, [ffmpeg](https://ffmpeg.org), an [Obsidian](https://obsidian.md) vault (a folder of markdown — no plugins needed).

1. Copy the two folders from `skills/` into `~/.claude/skills/`.
2. Edit `skills/obsidian-vault/SKILL.md` — set the vault path to your vault.
3. Create an **unlisted** YouTube playlist (e.g. "AI Queue"). Paste its URL into `skills/argus/SKILL.md` where marked. Unlisted means yt-dlp can read it with zero authentication — no cookies, no API keys, your account never touched.
4. Save videos to the playlist as you scroll. Then:

```
/argus <url>            # watch one video now
/argus <url> --frames   # force the frame pass
/argus queue            # drain the playlist
```

The vault teaches itself: open `Welcome.md`, click `Digest`, follow the links.

> **Note:** for the author's machine, the installed copies in `~/.claude/skills/` are canonical — this repo is the distributable, synced after changes.

## Anatomy

```
skills/
  argus/
    SKILL.md             # the pipeline: ledger → transcript → tier decision → note → cross-links → digest
    FRAMES.md            # the frame pass: scene detection, timestamp alignment, blind-spot stills
    clean_transcript.py  # collapses rolling auto-caption SRT into clean [m:ss] lines (~5-10x fewer tokens)
  obsidian-vault/
    SKILL.md       # vault path, conventions (MOCs, dossiers, frontmatter), retrieval workflow
```

Vault layout it produces:

```
Welcome.md         # home: topic index
Digest.md          # front page: every run, newest first
videos/            # one note per video (+ _processed.txt ledger)
topics/            # MOC index notes — one video appears in many
tools/             # auto-growing cross-video dossiers per tool
```
