"""Transcribe a media file with faster-whisper into `[m:ss] text` lines. Usage: transcribe_audio.py <media> [out.txt]"""
import sys

from faster_whisper import WhisperModel

model = WhisperModel("small", compute_type="int8")
segments, _info = model.transcribe(sys.argv[1])
lines = [f"[{int(s.start) // 60}:{int(s.start) % 60:02d}] {s.text.strip()}" for s in segments]
body = "\n".join(lines)
if len(sys.argv) > 2:
    open(sys.argv[2], "w", encoding="utf-8").write(body)
else:
    print(body)
