"""Collapse a caption file — YouTube auto-caption VTT or SRT, both rolling and
line-duplicated — into clean `[m:ss] text` lines.

Reads VTT natively so the caller never needs `--convert-subs` (an ffmpeg
postprocessor): captions work on a machine with no ffmpeg at all.

A path that does not exist is retried as a glob, so the caller never has to guess
yt-dlp's language suffix (`.en`, `.en-orig`, `.en-US`, `.en-GB`, ...).

Exits non-zero when nothing parses — an empty transcript must never look like success.

Temporally overlapping cues whose token edges share at least two words are
buffered into one passage. Exact duplicates also collapse while their cue times
overlap. Matching is local, so a phrase spoken again later is preserved.

Usage:
  clean_transcript.py <captions.vtt|captions.srt|<video id>> [out.txt]
"""
import re
import sys
from html import unescape
from pathlib import Path

STAMP = r"(\d+):(\d{2}):(\d{2})[.,](\d+)"
TIMING = re.compile(rf"{STAMP}\s*-->\s*{STAMP}")
TAGS = re.compile(r"<[^>]*>")   # VTT karaoke/styling: <c>, </c>, <00:00:01.500>, <i>


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
    line = unescape(line)
    return " ".join(line.split())


def seconds(parts):
    hours, minutes, whole, fraction = parts
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(whole)
        + float(f"0.{fraction}")
    )


def token_key(token):
    return token.casefold().strip(".,!?;:")


def overlap_size(existing, incoming):
    existing_keys = [token_key(token) for token in existing]
    incoming_keys = [token_key(token) for token in incoming]
    limit = min(len(existing_keys), len(incoming_keys))
    for size in range(limit, 0, -1):
        if existing_keys[-size:] == incoming_keys[:size]:
            return size
    return 0


def same_tokens(left, right):
    return [token_key(token) for token in left] == [
        token_key(token) for token in right
    ]


def parse(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        # The timing line may be preceded by an SRT index or a VTT cue id, or by
        # nothing at all — find it rather than assuming a position.
        idx = next((i for i, l in enumerate(lines) if TIMING.search(l)), None)
        if idx is None:
            continue
        match = TIMING.search(lines[idx])
        start = seconds(match.groups()[:4])
        end = seconds(match.groups()[4:])
        spoken = clean(" ".join(lines[idx + 1:]))
        if spoken:
            cues.append((start, end, spoken.split()))

    out = []
    current_start = None
    previous_end = None
    current_tokens = []
    for start, end, tokens in cues:
        overlap = 0
        if current_tokens and start < previous_end:
            overlap = overlap_size(current_tokens, tokens)
        rolling = overlap >= 2 or (
            overlap > 0
            and (
                same_tokens(current_tokens, tokens)
                or overlap == len(current_tokens)
                or overlap == len(tokens)
            )
        )
        if current_tokens and not rolling:
            out.append((current_start, " ".join(current_tokens)))
            current_start = None
            current_tokens = []
        if not current_tokens:
            current_start = start
            current_tokens = list(tokens)
        else:
            current_tokens.extend(tokens[overlap:])
        previous_end = end
    if current_tokens:
        out.append((current_start, " ".join(current_tokens)))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = resolve(sys.argv[1])
    print(f"clean_transcript: reading {src.name}", file=sys.stderr)

    rows = parse(src)
    if not rows:
        sys.exit(f"clean_transcript: parsed 0 caption lines from {src.name}. "
                 f"Treat this as no captions (fall through to audio), not as an empty video.")

    body = "\n".join(
        f"[{int(secs) // 60}:{int(secs) % 60:02d}] {text}"
        for secs, text in rows
    )
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(body, encoding="utf-8")
        print(f"clean_transcript: {len(rows)} lines -> {sys.argv[2]}", file=sys.stderr)
    else:
        print(body)
