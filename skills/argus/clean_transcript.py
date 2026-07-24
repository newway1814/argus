"""Collapse a caption file — YouTube auto-caption VTT or SRT, both rolling and
line-duplicated — into clean `[m:ss] text` lines.

Reads VTT natively so the caller never needs `--convert-subs` (an ffmpeg
postprocessor): captions work on a machine with no ffmpeg at all.

A path that does not exist is retried as a glob, so the caller never has to guess
yt-dlp's language suffix (`.en`, `.en-orig`, `.en-US`, `.en-GB`, ...).

Exits non-zero when nothing parses — an empty transcript must never look like success.

Usage:
  clean_transcript.py <captions.vtt|captions.srt|<video id>> [out.txt]
                      [--start SEC] [--end SEC]
"""
import argparse
import re
import sys
from collections import deque
from pathlib import Path

TIMING = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d+)\s*-->")
TAGS = re.compile(r"<[^>]*>")   # VTT karaoke/styling: <c>, </c>, <00:00:01.500>, <i>
ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&#39;": "'", "&quot;": '"'}
RECENT = 8                      # rolling-caption dedup window, in emitted lines


def resolve(arg):
    """The literal path, else the first caption file matching it as a prefix."""
    p = Path(arg)
    if p.is_file():
        return p
    stems = [p.name, p.stem, p.name.split(".")[0]]
    for stem in stems:
        for ext in (".vtt", ".srt"):
            hits = sorted(p.parent.glob(f"{stem}*{ext}"))
            if hits:
                return hits[0]
    sys.exit(f"clean_transcript: no caption file at {arg} (also tried {stems[-1]}*.vtt/.srt)")


def clean(line):
    line = TAGS.sub("", line)
    for entity, char in ENTITIES.items():
        line = line.replace(entity, char)
    return " ".join(line.split())


def parse(path, start=0.0, end=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    out, recent = [], deque(maxlen=RECENT)
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        # The timing line may be preceded by an SRT index or a VTT cue id, or by
        # nothing at all — find it rather than assuming a position.
        idx = next((i for i, l in enumerate(lines) if TIMING.search(l)), None)
        if idx is None:
            continue
        h, m, s, _ = TIMING.search(lines[idx]).groups()
        secs = int(h) * 3600 + int(m) * 60 + int(s)
        if secs < start or (end is not None and secs >= end):
            continue
        new = []
        for raw in lines[idx + 1:]:
            spoken = clean(raw)
            if spoken and spoken not in recent:
                new.append(spoken)
                recent.append(spoken)
        if new:
            out.append((secs, " ".join(new)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("captions")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    args = ap.parse_args()
    if args.start < 0:
        sys.exit(f"clean_transcript: window start must be nonnegative, got {args.start}")
    if args.end is not None and args.end <= args.start:
        sys.exit(
            f"clean_transcript: window end must be greater than start, "
            f"got {args.start} -> {args.end}"
        )

    src = resolve(args.captions)
    print(f"clean_transcript: reading {src.name}", file=sys.stderr)

    rows = parse(src, args.start, args.end)
    if not rows:
        sys.exit(
            f"clean_transcript: parsed 0 caption lines from {src.name} "
            f"inside the selected window. Treat this as no captions "
            f"(fall through to audio), not as an empty video."
        )

    body = "\n".join(f"[{secs // 60}:{secs % 60:02d}] {t}" for secs, t in rows)
    if args.output:
        Path(args.output).write_text(body, encoding="utf-8")
        print(f"clean_transcript: {len(rows)} lines -> {args.output}", file=sys.stderr)
    else:
        print(body)
