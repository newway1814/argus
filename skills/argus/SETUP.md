# First-run setup

Argus configures itself. Never send the user to edit files or read docs — detect, ask only what can't be detected, write the config, keep going with whatever they originally asked for.

**The bar: at most two questions, zero terminal detours.** And never dead-end — if a piece won't install, give the one-line fix for their OS and continue with the best output available (transcript-only note, `frames: no`, stub); a degraded note that names what would unlock full power beats a halt every time.

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

The token lives here and nowhere else — `telegram.py` reads it directly, so it never reaches a command line or a log. On macOS and Linux the file is written `chmod 600`; on Windows, keep it in the user profile (it already is) rather than a synced folder.

## No config at all (first ever run)

1. **Find the vault.** Read Obsidian's own registry — it lists every vault and which is open:
   - Windows: `%APPDATA%\obsidian\obsidian.json`
   - macOS: `~/Library/Application Support/obsidian/obsidian.json`
   - Linux: `~/.config/obsidian/obsidian.json`
   One vault → use it. Several → ask which. Obsidian not installed → offer to create a plain folder (default `~/Documents/Argus Vault`); it's ordinary markdown they can open in Obsidian anytime.
2. **Ask one placement question** if the chosen vault already has the user's own notes: file Argus material at the vault root, or under an `Argus/` subfolder? (Empty vault → root, don't ask.)
3. **Scaffold what's missing, never overwrite:** `videos/`, `topics/`, `tools/`, `Digest.md`, `Try Queue.md`, and a `Welcome.md` home note (skip if one exists).
4. **Check yt-dlp** (`yt-dlp --version`). Missing → ask once before installing, naming the command you will run. Argus arrives as a plugin from a marketplace, and running a package install on someone's machine on first use is theirs to approve, not ours to assume; note the answer so the question is asked once, not every run. Bare `pip install` is blocked on modern macOS/Debian (externally-managed environments), so walk the chain until one works:
   `pipx install yt-dlp` → `pip install --user yt-dlp` → `python -m pip install --user yt-dlp` → `winget install yt-dlp` / `brew install yt-dlp` / distro package. All fail → give the one-liner for their OS and stop the *install*, not the run: captions can still be attempted.
5. **Check Node** (`node --version`) — yt-dlp uses it to solve YouTube's player JS. Missing → don't block: say the one-liner (`winget install OpenJS.NodeJS.LTS` / `brew install node` / distro package), drop `--js-runtimes node` from calls, and proceed; if fetches then act flaky, remind them why.
6. **Resolve Python once and record it as `python_cmd`.** A machine usually has several interpreters, and "newest" is the wrong tie-breaker — the freshest one is the least likely to carry the dependencies. Pick by capability instead:
   - **Collect candidates.** `py -3`, `python3`, `python`, each with `--version`; keep those reporting 3.9 or newer. On Windows a usable runtime frequently exists while neither `python` nor `py` is on PATH, so also glob `%LOCALAPPDATA%\Programs\Python\Python3*\python.exe` and keep the absolute paths.
   - **Prefer one that already has the heavy dependency.** Run `<candidate> -c "import faster_whisper"` down the list and take the first that succeeds. Choosing on version alone picks, say, a 3.14 that has nothing installed over the 3.12 that has everything — and the mistake stays invisible until the first reel dies mid-drain.
   - **Nothing imports it?** Take the first ≥3.9 candidate. That is now the interpreter faster-whisper gets installed *into*, so install with `<python_cmd> -m pip install ...` and never a bare `pip`, which may well belong to a different interpreter and recreate the mismatch.

   Every bundled script is then called as `<python_cmd> "${CLAUDE_SKILL_DIR}/<script>.py"`. No candidate at all → say the one-line install (`winget install Python.Python.3.12` / `brew install python` / distro package); captions and metadata still work, but the frame, note, and Telegram helpers do not.
7. Write the config, then continue with the URL the user gave. Total user-facing cost: at most two questions.

## Lazy pieces — set up only when first needed

| Trigger | What to do |
|---|---|
| First frame pass — full video **or reel** — ffmpeg missing | Install per OS (`winget install Gyan.FFmpeg` / `brew install ffmpeg` / apt), with the user's OK. Declined or failed → transcript-only note, `frames: no`, and the note says what the frame pass would have added. Captions never need ffmpeg (`clean_transcript.py` reads VTT directly), so a machine without it still gets a full transcript note — only the eyes are missing. |
| First reel, faster-whisper missing | `<python_cmd> -m pip install faster-whisper` — always through the recorded interpreter, never a bare `pip`, or it lands in one Python while the skill runs in another. Then **prefetch the model in its own step**: `<python_cmd> "${CLAUDE_SKILL_DIR}/transcribe_audio.py" --prefetch`, allowing several minutes. Say the ~460MB download happens once. Skipping this makes the first real transcription look like a hang and time out mid-download. Failed → note from caption + frames, audio marked unread. |
| `/argus queue`, no `playlist_url` | Walk them through it in chat: YouTube → Library → New playlist → visibility **Unlisted** → paste the URL here. Explain why unlisted: readable with zero login, their account never touched. |
| `/argus queue`, no `telegram_token` | Offer the universal inbox: message @BotFather → `/newbot` → paste the token here. Write it to the config, then **pair the owner**: `<python_cmd> "${CLAUDE_SKILL_DIR}/telegram.py" pair` prints a one-time code for them to send to the bot, and binds only that account. Without the code, whoever finds the bot first would become its owner. From then on: Share → Telegram → their bot, from any app — and after every drain the bot messages back a digest. Tell them the honest limit: Telegram holds unread shares for 24 hours, so a drain at least daily keeps the inbox whole (anything drained is kept in the vault's `_inbox.jsonl` permanently). Skippable — the playlist alone is a fine queue. |

Never ask about a piece the user hasn't triggered. Done when the original request (watch this URL / drain the queue) has been fulfilled — setup is a detour, not a destination.
