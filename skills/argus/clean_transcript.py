"""Collapse a YouTube auto-caption SRT (rolling, duplicated lines) into clean `[m:ss] text` lines."""
import re
import sys


def parse(path):
    text = open(path, encoding="utf-8").read()
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    prev_lines = []
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.]", lines[1])
        if not m:
            continue
        secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        textlines = lines[2:]
        new = [t for t in textlines if t not in prev_lines]
        prev_lines = textlines
        if new:
            out.append((secs, " ".join(new)))
    return out


def fmt(s):
    return f"{s // 60}:{s % 60:02d}"


if __name__ == "__main__":
    rows = [f"[{fmt(s)}] {t}" for s, t in parse(sys.argv[1])]
    body = "\n".join(rows)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(body)
    else:
        print(body)
