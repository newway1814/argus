"""The one way a video note reaches the vault.

Owns everything about a note that must be identical every run: the item's
identity, the filename, the YAML frontmatter, and the write itself. The model
writes the body — the judgement — and nothing else touches disk.

Why a script rather than instructions:
  * A raw title can carry `:` `#` `"` or a newline, any of which silently breaks
    the frontmatter, and `[` `]` `#` `^` `|`, which break every `[[wikilink]]`
    pointing at the note — so the note becomes unreachable from its own MOC.
  * Windows rejects `<>:"/\\|?*`, reserved names (CON, NUL, COM1...), and
    trailing dots or spaces; OneDrive-hosted vaults sit deep enough that long
    titles hit the path limit.
  * A half-written note is worse than no note, so the write is atomic.
  * `type` and `watch-verdict` are enums. Validating them here is what keeps the
    prose in SKILL.md and argus-vault from drifting apart.

Usage:
  note_writer.py --vault <path> --meta meta.json --body body.md
  note_writer.py --identity "https://youtu.be/dQw4w9WgXcQ"   # -> youtube:dQw4w9WgXcQ

meta.json keys: title, channel, url, published (YYYY-MM-DD), duration, type,
tags (list), watch_verdict, frames (bool), plus optional processed, why_saved.
Identity and source are derived from url. Prints the note path and the exact
timestamp-link template to use in the body.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TYPES = ["tutorial", "news", "explainer", "opinion", "workflow"]
VERDICTS = ["skip", "skim", "watch", "try"]

# Windows-illegal, plus the characters that break Obsidian wikilinks.
STRIP = '<>:"/\\|?*[]#^'
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10))}
MAX_NAME = 120          # filename length cap, generous room for a deep vault path

INSTAGRAM = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([\w-]+)")
YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


class IdentityError(ValueError):
    """A recognized video platform URL that cannot identify one video."""


def parsed_url(url):
    candidate = url if "://" in url else f"https://{url}"
    return urlparse(candidate)


def youtube_identity(url):
    parsed = parsed_url(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in YOUTUBE_HOSTS | SHORT_HOSTS:
        return None
    if parsed.scheme not in {"http", "https"}:
        raise IdentityError("invalid YouTube video URL: only http and https are supported")

    segments = [segment for segment in parsed.path.split("/") if segment]
    source = "youtube"
    video_id = None

    if host in SHORT_HOSTS:
        if len(segments) == 1:
            video_id = segments[0]
    elif parsed.path.rstrip("/") == "/watch":
        candidates = parse_qs(parsed.query, keep_blank_values=True).get("v", [])
        if len(candidates) == 1:
            video_id = candidates[0]
    elif len(segments) == 2 and segments[0] in {"shorts", "live", "embed"}:
        video_id = segments[1]
        if segments[0] == "shorts":
            source = "youtube-shorts"

    if video_id is None or not YOUTUBE_ID.fullmatch(video_id):
        raise IdentityError(f"invalid YouTube video URL: {url}")
    return f"youtube:{video_id}", source


def identity_for(url):
    """`<source>:<id>` — the item's one name, in the ledger and in frontmatter."""
    youtube = youtube_identity(url)
    if youtube:
        return youtube
    m = INSTAGRAM.search(url)
    if m:
        return f"instagram:{m.group(1)}", "instagram"
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].split(".")[0] or "web"
    tail = re.sub(r"[^\w-]", "", url.rstrip("/").split("/")[-1])[:40] or "item"
    return f"{host}:{tail}", host


def link_template(identity, url):
    """Deep links are a YouTube affordance; inventing one elsewhere fabricates a URL."""
    source, _, vid = identity.partition(":")
    if source == "youtube":
        return f"https://youtu.be/{vid}?t={{seconds}}"
    return None


def safe_title(title, fallback):
    # Control characters become spaces rather than vanishing: dropping the
    # newline in "part 3/4\nsecond half" would glue it into "4second half".
    clean = "".join(" " if c in STRIP or unicodedata.category(c)[0] == "C" else c
                    for c in title)
    clean = re.sub(r"\s+", " ", clean).strip(" .")
    if clean.split(".")[0].lower() in RESERVED:
        clean = f"_{clean}"
    return clean or fallback


def yaml_scalar(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) or text in TYPES or text in VERDICTS:
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip() + '"'


def frontmatter(meta, identity, source):
    tags = meta.get("tags") or []
    rows = [
        ("identity", identity),
        ("title", meta.get("title", "")),
        ("channel", meta.get("channel", "")),
        ("url", meta.get("url", "")),
        ("source", source),
        ("published", meta.get("published", "")),
        ("processed", meta.get("processed") or date.today().isoformat()),
        ("duration", meta.get("duration", "")),
        ("type", meta["type"]),
        ("watch-verdict", meta["watch_verdict"]),
        ("frames", bool(meta.get("frames"))),
    ]
    body = "\n".join(f"{k}: {yaml_scalar(v)}" for k, v in rows)
    taglist = ", ".join(yaml_scalar(str(t)) for t in tags)
    return f"---\n{body}\ntags: [{taglist}]\n---\n"


def existing_identity(path):
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
    except OSError:
        return None
    m = re.search(r"^identity:\s*\"?([^\"\n]+)\"?", head, re.M)
    return m.group(1).strip() if m else None


def destination(vault, meta, identity):
    published = meta.get("published") or date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        sys.exit(f"note_writer: published must be YYYY-MM-DD, got {published!r}")
    vid = identity.partition(":")[2]
    folder = vault / "videos"

    # The limit that actually bites is the whole path, not the filename: a vault
    # inside OneDrive is already ~130 characters deep before the note is named.
    budget = min(MAX_NAME, 255 - len(str(folder.resolve())) - 1 - len(".md.tmp"))
    if budget < 24:
        sys.exit(f"note_writer: {folder} is too deep to name notes safely — "
                 "move the vault closer to the drive root")

    def build(suffix=""):
        room = budget - len(published) - len(" - ") - len(suffix)
        title = safe_title(meta.get("title", ""), vid)[:max(room, 1)].rstrip(" .")
        return folder / f"{published} - {title}{suffix}.md"

    target = build()
    # Same item reprocessed -> overwrite. Different item, same title -> disambiguate.
    if target.exists() and existing_identity(target) not in (None, identity):
        target = build(f" ({vid})")
    return target


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity", help="print `<source>:<id>` for a URL and exit")
    ap.add_argument("--vault")
    ap.add_argument("--meta")
    ap.add_argument("--body")
    args = ap.parse_args()

    if args.identity:
        try:
            identity, source = identity_for(args.identity)
        except IdentityError as error:
            sys.exit(f"note_writer: {error}")
        print(f"identity: {identity}")
        print(f"source: {source}")
        tmpl = link_template(identity, args.identity)
        print(f"link: {tmpl}" if tmpl else
              "link: none - cite moments as plain [m:ss], this source has no timestamp links")
        return

    if not (args.vault and args.meta and args.body):
        sys.exit("note_writer: --vault, --meta and --body are all required")

    try:
        meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"note_writer: no meta file at {args.meta}")
    except json.JSONDecodeError as e:
        sys.exit(f"note_writer: {args.meta} is not valid JSON ({e}). "
                 "A raw newline inside a string is the usual cause — escape it as \\n.")
    for field in ("url", "type", "watch_verdict"):
        if not meta.get(field):
            sys.exit(f"note_writer: meta.json is missing {field}")
    if meta["type"] not in TYPES:
        sys.exit(f"note_writer: type must be one of {'|'.join(TYPES)}, got {meta['type']!r}")
    if meta["watch_verdict"] not in VERDICTS:
        sys.exit(f"note_writer: watch-verdict must be one of {'|'.join(VERDICTS)}, "
                 f"got {meta['watch_verdict']!r}")

    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        sys.exit(f"note_writer: no vault at {vault}")

    try:
        identity, source = identity_for(meta["url"])
    except IdentityError as error:
        sys.exit(f"note_writer: {error}")
    body = Path(args.body).read_text(encoding="utf-8")
    body = re.sub(r"\A---\n.*?\n---\n", "", body, flags=re.S)   # body only; we own the frontmatter
    dest = destination(vault, meta, identity)
    write_atomic(dest, frontmatter(meta, identity, source) + "\n" + body.lstrip("\n"))

    print(f"note: {dest}")
    print(f"identity: {identity}")
    tmpl = link_template(identity, meta["url"])
    print(f"link: {tmpl}" if tmpl else
          "link: none - cite moments as plain [m:ss], this source has no timestamp links")


if __name__ == "__main__":
    main()
