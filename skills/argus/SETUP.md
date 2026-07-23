# First-run configuration

Argus configures its own files. The user prepares and owns Python and every external dependency. Never invoke `pip`, `pipx`, `brew`, `winget`, `apt`, or another package manager. Detect what is ready, ask only what cannot be detected, write Argus config, and continue only with capabilities the machine actually has.

**The bar after prerequisites are ready: at most two questions and zero terminal detours during normal watching.** If a prerequisite is missing, name the unavailable capability and give one exact preparation command for the user's OS without running it. Continue with a valid degraded path when one exists. If the requested output cannot be produced, stop and say it was not completed.

Config lives at `~/.claude/argus.config.json`:

```json
{
  "vault_path": "",
  "python_cmd": "",
  "playlist_url": "",
  "telegram_token": "",
  "telegram_owner_id": null,
  "telegram_offset": 0
}
```

The token lives here and nowhere else, `telegram.py` reads it directly, so it never reaches a command line or a log. On macOS and Linux the file is written `chmod 600`; on Windows, keep it in the user profile (it already is) rather than a synced folder.

## No config at all (first ever run)

1. **Find the vault.** Read Obsidian's own registry, it lists every vault and which is open:
   - Windows: `%APPDATA%\obsidian\obsidian.json`
   - macOS: `~/Library/Application Support/obsidian/obsidian.json`
   - Linux: `~/.config/obsidian/obsidian.json`
   One vault → use it. Several → ask which. Obsidian not installed → offer to create a plain folder (default `~/Documents/Argus Vault`); it's ordinary markdown they can open in Obsidian anytime.
2. **Ask one placement question** if the chosen vault already has the user's own notes: file Argus material at the vault root, or under an `Argus/` subfolder? (Empty vault → root, don't ask.)
3. **Scaffold what's missing, never overwrite:** `videos/`, `topics/`, `tools/`, `Digest.md`, `Try Queue.md`, and a `Welcome.md` home note (skip if one exists).
4. **Check yt-dlp** (`yt-dlp --version`). Missing → explain that Argus cannot fetch the video or captions, give one preparation command appropriate to the user's OS, and stop the requested run. Do not run the command. Do not mark setup or the video request successful.
5. **Check Node** (`node --version`), yt-dlp uses it to solve YouTube's player JS. Missing → don't block: say the one-liner (`winget install OpenJS.NodeJS.LTS` / `brew install node` / distro package), drop `--js-runtimes node` from calls, and proceed; if fetches then act flaky, remind them why.
6. **Resolve Python once and record it as `python_cmd`.** A machine usually has several interpreters, and "newest" is the wrong tie-breaker, the freshest one is the least likely to carry the dependencies. Pick by capability instead:
   - **Collect candidates.** `py -3`, `python3`, `python`, each with `--version`; keep those reporting 3.9 or newer. On Windows a usable runtime frequently exists while neither `python` nor `py` is on PATH, so also glob `%LOCALAPPDATA%\Programs\Python\Python3*\python.exe` and keep the absolute paths.
   - **Prefer one that already has the heavy dependency.** Run `<candidate> -c "import faster_whisper"` down the list and take the first that succeeds. Choosing on version alone picks, say, a 3.14 that has nothing installed over the 3.12 that has everything, and the mistake stays invisible until the first reel dies mid-drain.
   - **Nothing imports it?** Take the first ≥3.9 candidate for the core bundled scripts. Record that local transcription is unavailable. Do not install faster-whisper.

   Every bundled script is then called as `<python_cmd> "${CLAUDE_SKILL_DIR}/<script>.py"`. No candidate at all → give one Python preparation command for the user's OS and stop. The serializer cannot write a valid Argus note without Python, so do not pretend captions or metadata alone completed the request.
7. Write the config, then continue with the URL the user gave using only verified capabilities. Total user-facing cost after prerequisites are ready: at most two questions.

## Lazy pieces, set up only when first needed

| Trigger | What to do |
|---|---|
| First frame pass, full video **or reel**, ffmpeg missing | Give one preparation command for the user's OS, but do not run it. Continue with a transcript-only note, set `frames: no`, and state what the frame pass could not verify. Captions never need ffmpeg (`clean_transcript.py` reads VTT directly), so a machine without it still gets a full transcript note, only the eyes are missing. |
| First reel or caption-less video, faster-whisper missing | Explain that local audio transcription is unavailable and give the exact command for preparing the recorded Python environment, but do not run it. Use captions and frames if they exist. If the item has no readable speech source, write the documented stub and mark audio unread. Model prefetch is a separate explicit user action, never part of an unrelated video run. |
| `/argus queue`, no `playlist_url` | Walk them through it in chat: YouTube → Library → New playlist → visibility **Unlisted** → paste the URL here. Explain why unlisted: readable with zero login, their account never touched. |
| `/argus queue`, no `telegram_token` | Offer the universal inbox: message @BotFather → `/newbot` → paste the token here. Write it to the config, then **pair the owner**: `<python_cmd> "${CLAUDE_SKILL_DIR}/telegram.py" pair` prints a one-time code for them to send to the bot, and binds only that account. Without the code, whoever finds the bot first would become its owner. From then on: Share → Telegram → their bot, from any app, and after every drain the bot messages back a digest. Tell them the honest limit: Telegram holds unread shares for 24 hours, so a drain at least daily keeps the inbox whole (anything drained is kept in the vault's `_inbox.jsonl` permanently). Skippable, the playlist alone is a fine queue. |

Never ask about a piece the user hasn't triggered. Done only when the original request (watch this URL / drain the queue) has been fulfilled with the capabilities reported in the note. A prerequisite explanation is not successful setup, and a stub is not a watched video.
