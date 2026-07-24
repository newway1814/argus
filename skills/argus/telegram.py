"""The only thing that touches the Telegram token.

The token is a bearer credential that Telegram puts in the request *path*, so any
call the model composes puts the secret into a command line, a tool log, and the
transcript. This script reads it from the config itself and never prints a URL —
the model asks for inbox items or sends a digest, and never sees the token.

Durability: the Bot API drops updates after 24 hours, and reading them with an
offset deletes them server-side — so a drain that crashes after advancing the
offset would lose the queue permanently. Every item is therefore written to
`<vault>/_inbox.jsonl` and fsynced *before* the offset moves. Telegram is
transport; the vault is the queue.

Pairing: the owner is confirmed with a one-time code, so whoever finds the bot
first cannot bind themselves as owner.

Usage:
  telegram.py pair            # confirm who owns this bot, once
  telegram.py fetch           # durable inbox -> prints items not yet in the ledger
  telegram.py send --file digest.txt
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from note_writer import IdentityError, identity_for  # noqa: E402

CONFIG = Path.home() / ".claude" / "argus.config.json"
URLS = re.compile(r"https?://\S+")
POLL_SECONDS = 300   # the code reaches the user through an agent turn; 2 minutes is not enough


def load():
    if not CONFIG.is_file():
        sys.exit(f"telegram: no config at {CONFIG} — run first-run setup")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not cfg.get("telegram_token"):
        sys.exit("telegram: no telegram_token in config — the playlist door still works")
    return cfg


def save(cfg):
    tmp = CONFIG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG)
    try:
        os.chmod(CONFIG, 0o600)   # no-op on Windows; harmless
    except OSError:
        pass


def call(cfg, method, params=None, timeout=30):
    """One Bot API call. Errors never quote the URL — it contains the token."""
    url = f"https://api.telegram.org/bot{cfg['telegram_token']}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data),
                                    timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit("telegram: token rejected (401) — regenerate it with @BotFather")
        if e.code == 409:
            sys.exit("telegram: 409 conflict — this bot has a webhook set, so getUpdates "
                     "is disabled. Call deleteWebhook on it, then retry.")
        sys.exit(f"telegram: {method} failed with HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"telegram: network error on {method}: {e.reason if hasattr(e, 'reason') else e}")


def inbox_path(cfg):
    vault = Path(cfg.get("vault_path", "")).expanduser()
    if not vault.is_dir():
        sys.exit("telegram: vault_path in config does not exist — run first-run setup")
    return vault / "_inbox.jsonl"


def append_durable(path, records):
    """Write and fsync before any offset moves. This is the whole durability story."""
    if not records:
        return
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def harvest(cfg, updates, owner_only=True):
    records, high = [], cfg.get("telegram_offset", 0)
    for upd in updates:
        high = max(high, upd.get("update_id", 0))
        msg = upd.get("message") or upd.get("channel_post") or {}
        sender = (msg.get("from") or {}).get("id")
        owner = cfg.get("telegram_owner_id")
        if owner_only and owner and sender != owner:
            continue
        text = " ".join(filter(None, [msg.get("text"), msg.get("caption")]))
        for url in URLS.findall(text):
            url = url.rstrip(".,)")
            try:
                identity, _ = identity_for(url)
            except IdentityError:
                continue
            records.append({
                "update_id": upd.get("update_id"),
                "received": msg.get("date"),
                "url": url,
                "identity": identity,
                "comment": URLS.sub("", text).strip(),
                "from_id": sender,
            })
    return records, high


def ledger_ids(cfg):
    ledger = Path(cfg["vault_path"]).expanduser() / "videos" / "_processed.txt"
    if not ledger.is_file():
        return set()
    return {l.strip() for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()}


def cmd_fetch(cfg):
    offset = cfg.get("telegram_offset", 0)
    res = call(cfg, "getUpdates", {"offset": offset + 1, "timeout": 0})
    if not res.get("ok"):
        sys.exit("telegram: getUpdates returned not-ok")

    records, high = harvest(cfg, res.get("result", []))
    path = inbox_path(cfg)
    append_durable(path, records)          # durable first...
    if high > offset:
        cfg["telegram_offset"] = high      # ...then let Telegram forget them
        save(cfg)

    done = ledger_ids(cfg)
    pending, seen = [], set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            ident = rec["identity"]
            bare = ident.partition(":")[2]
            if ident in done or bare in done or ident in seen:
                continue
            seen.add(ident)
            pending.append(rec)

    print(f"new: {len(records)}  pending: {len(pending)}  inbox: {path}")
    for rec in pending:
        comment = f"  # {rec['comment']}" if rec["comment"] else ""
        print(f"{rec['identity']}\t{rec['url']}{comment}")


def cmd_pair(cfg):
    code = f"{random.randint(100000, 999999)}"
    print(f"Send this code to the bot as a message: {code}", flush=True)
    print(f"Waiting up to {POLL_SECONDS}s...", flush=True)
    deadline = time.time() + POLL_SECONDS
    offset = cfg.get("telegram_offset", 0)
    seen = {}   # update_id -> record, buffered until we know whose they are
    while time.time() < deadline:
        res = call(cfg, "getUpdates", {"offset": offset + 1, "timeout": 10}, timeout=30)
        updates = res.get("result", [])
        # The offset deliberately does not move while pairing is unresolved:
        # advancing it is what tells Telegram to forget these updates, and a
        # pairing that times out must not take the user's pending shares with it.
        records, high = harvest(cfg, updates, owner_only=False)
        for rec in records:
            seen[rec["update_id"]] = rec
        for upd in updates:
            msg = upd.get("message") or {}
            if code in (msg.get("text") or ""):
                owner = (msg.get("from") or {}).get("id")
                mine = [r for r in seen.values() if r["from_id"] == owner]
                if cfg.get("vault_path") and mine:
                    append_durable(inbox_path(cfg), mine)   # durable before the offset moves
                cfg["telegram_owner_id"] = owner
                cfg["telegram_offset"] = high
                save(cfg)
                print(f"paired: owner id {owner}. Only this account is read.", flush=True)
                if mine:
                    print(f"kept {len(mine)} shared link(s) already waiting in the bot", flush=True)
                return
        time.sleep(3)
    sys.exit("telegram: no code received in time. Nothing was paired and nothing was "
             "consumed; the queue is untouched. Run pair again.")


def cmd_send(cfg, file):
    if not cfg.get("telegram_owner_id"):
        sys.exit("telegram: not paired yet — run `telegram.py pair` first")
    text = Path(file).read_text(encoding="utf-8")
    res = call(cfg, "sendMessage", {
        "chat_id": cfg["telegram_owner_id"],
        "text": text,
        "disable_web_page_preview": "true",
    })
    print("sent" if res.get("ok") else "not sent — Digest.md remains the front page")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["pair", "fetch", "send"])
    ap.add_argument("--file", help="digest text to send")
    args = ap.parse_args()

    config = load()
    if args.command == "pair":
        cmd_pair(config)
    elif args.command == "fetch":
        cmd_fetch(config)
    else:
        if not args.file:
            sys.exit("telegram: send needs --file")
        cmd_send(config, args.file)
