# First-run setup

Argus configures itself. Never send the user to edit files or read docs — detect, ask only what can't be detected, write the config, keep going with whatever they originally asked for.

**The bar: at most two questions, zero terminal detours.** And never dead-end — if a piece won't install, give the one-line fix for their OS and continue with the best output available (transcript-only note, `frames: no`, stub); a degraded note that names what would unlock full power beats a halt every time.

Config lives at `~/.claude/argus.config.json`:

```json
{
  "vault_path": "",
  "playlist_url": "",
  "telegram_token": "",
  "telegram_bot": "",
  "telegram_owner_id": null,
  "telegram_offset": 0
}
```

## No config at all (first ever run)

1. **Find the vault.** Read Obsidian's own registry — it lists every vault and which is open:
   - Windows: `%APPDATA%\obsidian\obsidian.json`
   - macOS: `~/Library/Application Support/obsidian/obsidian.json`
   - Linux: `~/.config/obsidian/obsidian.json`
   One vault → use it. Several → ask which. Obsidian not installed → offer to create a plain folder (default `~/Documents/Argus Vault`); it's ordinary markdown they can open in Obsidian anytime.
2. **Ask one placement question** if the chosen vault already has the user's own notes: file Argus material at the vault root, or under an `Argus/` subfolder? (Empty vault → root, don't ask.)
3. **Scaffold what's missing, never overwrite:** `videos/`, `topics/`, `tools/`, `Digest.md`, `Try Queue.md`, and a `Welcome.md` home note (skip if one exists).
4. **Check yt-dlp** (`yt-dlp --version`). Missing → install it, telling the user, not asking (it's the tool's core dependency). Bare `pip install` is blocked on modern macOS/Debian (externally-managed environments), so walk the chain until one works:
   `pipx install yt-dlp` → `pip install --user yt-dlp` → `python -m pip install --user yt-dlp` → `winget install yt-dlp` / `brew install yt-dlp` / distro package. All fail → give the one-liner for their OS and stop the *install*, not the run: captions can still be attempted.
5. **Check Node** (`node --version`) — yt-dlp uses it to solve YouTube's player JS. Missing → don't block: say the one-liner (`winget install OpenJS.NodeJS.LTS` / `brew install node` / distro package), drop `--js-runtimes node` from calls, and proceed; if fetches then act flaky, remind them why.
6. Write the config, then continue with the URL the user gave. Total user-facing cost: at most two questions.

## Lazy pieces — set up only when first needed

| Trigger | What to do |
|---|---|
| First frame pass, ffmpeg missing | Install per OS (`winget install Gyan.FFmpeg` / `brew install ffmpeg` / apt), with the user's OK. Declined or failed → transcript-only note, `frames: no`, and the note says what the frame pass would have added. |
| First reel, faster-whisper missing | `pip install faster-whisper` (same fallback chain as yt-dlp; say the small model downloads ~500MB once). Failed → note from caption + frames, audio marked unread. |
| `/argus queue`, no `playlist_url` | Walk them through it in chat: YouTube → Library → New playlist → visibility **Unlisted** → paste the URL here. Explain why unlisted: readable with zero login, their account never touched. |
| `/argus queue`, no `telegram_token` | Offer the universal inbox: message @BotFather → `/newbot` → paste the token here. From then on: Share → Telegram → their bot, from any app — and after every drain the bot messages back a digest of what was watched. Skippable — the playlist alone is a fine queue. |

Never ask about a piece the user hasn't triggered. Done when the original request (watch this URL / drain the queue) has been fulfilled — setup is a detour, not a destination.
