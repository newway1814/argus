"""Collapse YouTube auto-caption VTT or SRT into clean `[m:ss] text` lines.

Reads VTT natively so captions work without ffmpeg. A path that does not exist
is retried as a glob, so callers do not need to guess yt-dlp's language suffix.

Temporally overlapping cues whose token edges share at least two words are
buffered into one passage. Exact duplicates also collapse while their cue times
overlap. Matching is local, so a phrase spoken again later is preserved.

Exits nonzero when nothing parses. An empty transcript must not look successful.

Usage:
  clean_transcript.py <captions.vtt|captions.srt|<video id>> [out.txt]
                      [--start SEC] [--end SEC] [--duration SEC]
"""
import argparse
import math
import re
import sys
from html import unescape
from pathlib import Path

STAMP = r"(\d+):(\d{2}):(\d{2})[.,](\d+)"
TIMING = re.compile(rf"{STAMP}\s*-->\s*{STAMP}")
TAGS = re.compile(r"<[^>]*>")


def resolve(arg):
    """Return a literal caption path or the first matching language suffix."""
    path = Path(arg)
    if path.is_file():
        return path
    stems = [path.name, path.stem, path.name.split(".")[0]]
    for stem in stems:
        for extension in (".vtt", ".srt"):
            hits = sorted(path.parent.glob(f"{stem}*{extension}"))
            if hits:
                return hits[0]
    sys.exit(
        f"clean_transcript: no caption file at {arg} "
        f"(also tried {stems[-1]}*.vtt/.srt)"
    )


def clean(line):
    return " ".join(unescape(TAGS.sub("", line)).split())


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


def parse(path, window_start=0.0, window_end=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line for line in block.splitlines() if line.strip()]
        index = next(
            (i for i, line in enumerate(lines) if TIMING.search(line)),
            None,
        )
        if index is None:
            continue
        match = TIMING.search(lines[index])
        cue_start = seconds(match.groups()[:4])
        cue_end = seconds(match.groups()[4:])
        if cue_start < window_start:
            continue
        if window_end is not None and cue_start >= window_end:
            continue
        spoken = clean(" ".join(lines[index + 1:]))
        if spoken:
            cues.append((cue_start, cue_end, spoken.split()))

    output = []
    current_start = None
    previous_end = None
    current_tokens = []
    for cue_start, cue_end, tokens in cues:
        overlap = 0
        if current_tokens and cue_start < previous_end:
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
            output.append((current_start, " ".join(current_tokens)))
            current_start = None
            current_tokens = []
        if not current_tokens:
            current_start = cue_start
            current_tokens = list(tokens)
        else:
            current_tokens.extend(tokens[overlap:])
        previous_end = cue_end
    if current_tokens:
        output.append((current_start, " ".join(current_tokens)))
    return output


def validate_window(start, end, duration):
    values = [value for value in (start, end, duration) if value is not None]
    if not all(math.isfinite(value) for value in values):
        sys.exit("clean_transcript: window values must be finite numbers")
    if start < 0:
        sys.exit(
            f"clean_transcript: window start must be nonnegative, got {start}"
        )
    if end is not None and end <= start:
        sys.exit(
            f"clean_transcript: window end must be greater than start, "
            f"got {start} -> {end}"
        )
    if end is not None and duration is None:
        sys.exit("clean_transcript: --duration is required when --end is set")
    if duration is not None and duration <= 0:
        sys.exit(
            f"clean_transcript: source duration must be greater than zero, "
            f"got {duration}"
        )
    if end is not None and end > duration:
        sys.exit(
            f"clean_transcript: window end {end} exceeds "
            f"{duration} source duration"
        )


def timestamp(secs):
    whole = int(secs)
    millis = round((secs - whole) * 1000)
    suffix = f".{millis:03d}" if millis else ""
    return f"{whole // 60}:{whole % 60:02d}{suffix}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("captions")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--duration", type=float, help="source duration in seconds")
    args = parser.parse_args()

    validate_window(args.start, args.end, args.duration)
    source = resolve(args.captions)
    print(f"clean_transcript: reading {source.name}", file=sys.stderr)
    rows = parse(source, args.start, args.end)
    if not rows:
        sys.exit(
            f"clean_transcript: parsed 0 caption lines from {source.name} "
            f"inside the selected window. Treat this as no captions "
            f"(fall through to audio), not as an empty video."
        )

    body = "\n".join(
        f"[{timestamp(secs)}] {text}"
        for secs, text in rows
    )
    if args.output:
        Path(args.output).write_text(body, encoding="utf-8")
        print(
            f"clean_transcript: {len(rows)} lines -> {args.output}",
            file=sys.stderr,
        )
    else:
        print(body)


if __name__ == "__main__":
    main()
