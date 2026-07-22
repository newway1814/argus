---
name: argus
description: Watch a YouTube video — transcript plus on-screen frames — and file what it teaches into the Obsidian vault. Use when the user gives a YouTube URL to watch/process/take notes on, or asks to drain the watch queue.
---

# Argus

The hundred-eyed watchman: watches YouTube so the user doesn't have to, and files everything for later retrieval. Vault path and conventions live in the **obsidian-vault** skill — follow it for all writing and linking.

Usage: `/argus <url>` · `/argus <url> --frames` (force the frame pass) · `/argus queue`

Queue playlist (unlisted): `TODO — user has not created the playlist yet; ask for the URL and replace this line.`

Download into the scratchpad only; delete media once the note is written.

## Single video

1. **Ledger check.** Extract the video ID. If it is in `videos/_processed.txt`, report the existing note and stop.
2. **Tier 1 — transcript.**
   ```
   yt-dlp --skip-download --write-auto-subs --write-subs --sub-langs "en.*,en" --convert-subs srt -o "%(id)s" <url>
   yt-dlp --skip-download --print "%(title)s | %(channel)s | %(upload_date)s | %(duration_string)s" <url>
   ```
   Read the `.srt`. Done when you can state the video's type (tutorial | news | explainer | opinion) and a 3-sentence TL;DR.
3. **Tier decision.** Run the frame pass if the type is tutorial/demo, the transcript points at the screen ("as you can see", "click here", "this code", "paste this"), or `--frames` was passed. A talking head with nothing on screen resolves at Tier 1 — record `frames: no` in the note.
4. **Frame pass.** Follow [FRAMES.md](FRAMES.md).
5. **Write the note** to `videos/YYYY-MM-DD - <Title>.md` (published date) using the template below. Verdict bar: `watch` is rare — only when doing beats reading (hands-on feel, dense visual demos); always name the exact minute ranges worth the eyeballs.
6. **Cross-link.** Create or append a `tools/` dossier for every tool named in the note; link the note from every `topics/` MOC it touches (creating MOCs per obsidian-vault rules). Done when every named tool has a dossier entry and the note is reachable from at least one MOC.
7. **Digest + ledger.** Prepend the run's entry below the `---` in `Digest.md`: date, `[[note]]`, TL;DR line, verdict. Append the video ID to `videos/_processed.txt`. Delete downloaded media. End with a chat summary: what was watched, the verdict, anything flagged outdated.

## Queue drain (`/argus queue`)

1. `yt-dlp --flat-playlist --print id <playlist-url>` → drop IDs already in the ledger.
2. Run the single-video flow on each remaining ID, oldest first.
3. One combined Digest entry and one chat summary: N videos, which (if any) earned `watch` and why. Done when the ledger contains every playlist ID.

## Note template

```markdown
---
title:
channel:
url: https://youtu.be/<id>
published: YYYY-MM-DD
processed: YYYY-MM-DD
duration:
type: tutorial | news | explainer | opinion
tags: []
watch-verdict: skip | skim | watch
frames: yes | no
---

## TL;DR
(≤3 sentences)

## Watch verdict
Verdict + the minute ranges that deserve eyeballs, or why none do.

## Prerequisites            <!-- tutorials: what the video assumes installed / signed up / known -->

## Runbook                  <!-- tutorials: reproducible WITHOUT watching -->
1. Numbered steps with exact commands, config, and UI locations, quoted from frames.

## Outdated flags
Stale syntax, renamed flags, deprecated models/APIs — or "None spotted".

## Key claims & facts       <!-- news/explainers -->
- Claim — [mm:ss](https://youtu.be/<id>?t=<seconds>)

## Tools & projects
- [[ToolName]] — what this video said about it

## Timestamps
- [mm:ss](https://youtu.be/<id>?t=<seconds>) — moment worth jumping to
```
