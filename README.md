# Argus 👁️

**See it → 2 taps → forget it.** Argus is a [Claude Code](https://claude.com/claude-code) plugin that *watches* YouTube videos and Instagram reels for you — transcript **and** on-screen frames — and turns them into **runbooks**: the exact commands, configs, and steps, reproducible without ever pressing play. Everything files into a plain-markdown vault you can query forever.

Named after Argus Panoptes, the watchman of Greek myth whose hundred eyes never all slept at once.

## The problem

Staying current with AI means watching YouTube: tutorials, workflow demos, news breakdowns. Forty videos a month is ~13 hours of watching. Realistically you watch a handful, feel guilty about the rest, and three months later you can't remember which video showed the exact config you now desperately need. Your saved reels? A graveyard you never reopen.

And summarizer tools can't fix this, because they read the transcript and stop — but in tutorials the payload is *on the screen*: the command typed, the config pasted, the menu clicked. The speaker just says "then you paste this in." **The transcript never contains *this*.** Argus reads the frames beside the words spoken at each timestamp — that's the difference.

## The 10-second pitch

**On your phone**, whenever something looks useful:

- YouTube video or Short: **Share → Save to playlist.** Two taps.
- Instagram reel: **Share → Telegram → your bot.** Three taps.

**At your desk**, whenever you feel like it:

```
/argus queue
```

Argus watches everything you saved, writes a note per item, messages you a digest on Telegram, and tells you the *rare* minutes actually worth your eyeballs. Or process any single link directly, no queue needed:

```
/argus <url>
```

## What a note contains

Every watched item becomes a retrieval-grade note, not a summary:

- a 3-sentence **TL;DR**
- a **runbook** — numbered steps with the *exact* commands, config, and UI paths read off the frames, reproducible without watching
- **prerequisites** and **outdated flags** (AI tutorials rot in weeks — Argus says so)
- deep-linked timestamps (`?t=862`) so "pull up the video" means landing at 14:22, not scrubbing from 0:00
- a **watch-verdict**: `skip` / `skim` / `watch` / `try` — `watch` is rare and comes with exact minute ranges; workflows worth attempting land in a **Try Queue** with one nominated experiment per week
- **cross-links**: topic index notes, and per-tool **dossier pages** that automatically accumulate what every video ever said about LangGraph, Firecrawl, whatever

## Install — two commands, inside Claude Code

```
/plugin marketplace add newway1814/argus
/plugin install argus@argus
```

**Requirements: Claude Code, Python 3.9+, and Node.** Everything else installs itself the first time it's needed.

Then paste any link:

```
/argus <url>
```

On first run Argus configures *itself*, in the same conversation: it finds your Obsidian vault by reading Obsidian's own config (or creates a plain markdown folder if you don't use Obsidian), scaffolds the note structure, and installs yt-dlp. **At most two questions, zero terminal detours — anything beyond that is a bug, please file an issue.**

<details>
<summary>Manual install (no plugin system)</summary>

Copy both folders from `skills/` into `~/.claude/skills/` — you need **both**: `argus` (the watcher) and `argus-vault` (the vault conventions and retrieval).

</details>

## The three levels

Each level is opt-in and sets itself up in chat the first time you reach for it. Level 1 is a complete product on its own.

**Level 1 — paste a link.** `/argus <url>`. First tutorial triggers a one-time ffmpeg install (with your OK) for the frame pass; first reel installs faster-whisper for local audio transcription.

**Level 2 — the YouTube queue.** First `/argus queue` walks you through creating an **unlisted** playlist (readable with zero login — no cookies, no API keys, your account never touched). From then on, saving a video is two taps and draining is one command.

**Level 3 — the Telegram inbox + digest.** Optional, one minute with @BotFather. Your bot becomes a universal inbox — **Share → Telegram → bot, from any app** (this is what catches Instagram reels) — *and* an outbox: after every drain it messages you a digest — what was watched, this week's experiment to try, and the few minutes worth actual eyeballs.

## The payoff — retrieval

Weeks later you hit a wall and ask, in any Claude Code session:

> "have I watched anything about MCP tool permissions?"

The `argus-vault` skill greps the vault — tool dossiers first, then topics, then videos — and answers **from your notes**, citing the exact note and timestamp. No embeddings, no vector database, no RAG pipeline: plain markdown, wikilinks, and text search (the [Karpathy LLM-wiki](https://github.com/green-dalii/obsidian-llm-wiki) philosophy). At personal scale, a well-linked folder of text beats a vector store on every axis — and any agent can read it.

The system is honest about what it is: a *reference system with a triage layer*, not a magic learning machine. The agent watches everything; you learn at the moment of need — which is when learning sticks anyway.

## Costs and conduct — stated plainly

**Tokens.** Tier 1 (transcript-only) is cheap. The frame pass reads 30–80 frames and costs roughly a long Claude Code session per tutorial; the frame budget is hard-capped at 80 regardless of video length, and videos over 60 minutes stay transcript-only unless you force `--frames`. Anything over ~90 minutes stops and asks first — it tells you the cost and offers to process by the video's own chapters (one note, a section per chapter), because a marathon lecture is a season, not an episode. Drain a big queue on a day you're not racing your usage limits.

**Fetching.** Argus is a personal-use tool built for respectful fetching *by design*: it downloads anonymously, never uses your cookies or login, never retries blocked content with credentials, and the queue works off an unlisted playlist precisely so your account is never touched. Media is deleted the moment the note is written. What you save, watch, and store is your business — literally: it all lives in plain files on your machine.

**Failure policy.** Argus never dead-ends. A missing dependency gets one auto-install attempt, then the exact one-line fix for your OS — and you still get the best note your machine can currently produce, honestly flagged with what's missing.

## Anatomy

```
skills/
  argus/
    SKILL.md             # the pipeline: ledger → transcript → tier decision → note → cross-links → digest
    SETUP.md             # self-configuring first run + lazy per-feature setup
    FRAMES.md            # the frame pass: scene scoring, timestamp alignment, blind-spot stills
    REELS.md             # reels/Shorts: speech + burned-in overlays + caption, aligned
    extract_frames.py    # single-decode scene scoring: burst collapse, budget cap, gap report
    clean_transcript.py  # collapses rolling auto-caption SRT into clean [m:ss] lines (~5-10x fewer tokens)
    transcribe_audio.py  # local faster-whisper transcription for reels and caption-less videos
  argus-vault/
    SKILL.md             # vault conventions (MOCs, dossiers, Try Queue) + the retrieval workflow
```

Vault layout it produces:

```
Welcome.md         # home: topic index
Digest.md          # front page: every run, newest first
Try Queue.md       # saved workflows; one weekly pick
videos/            # one note per video/reel (+ _processed.txt ledger)
topics/            # MOC index notes — one video appears in many
tools/             # auto-growing cross-video dossiers per tool
```
