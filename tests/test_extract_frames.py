import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT_FRAMES = ROOT / "skills" / "argus" / "extract_frames.py"


class ExtractFramesCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.out = self.root / "frames"
        self.video = self.root / "unreadable.mp4"
        self.bin.mkdir()
        self.video.write_bytes(b"not real video data")

    def executable(self, name, body):
        if os.name == "nt":
            path = self.bin / f"{name}.cmd"
            path.write_text(f"@echo off\r\n{body}\r\n", encoding="utf-8")
        else:
            path = self.bin / name
            path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            path.chmod(0o755)
        return path

    def test_successful_ffmpeg_without_a_frame_is_reported_as_failure(self):
        self.executable("ffprobe", "echo 120")
        self.executable("ffmpeg", "exit /b 0" if os.name == "nt" else "exit 0")
        env = os.environ.copy()
        env["PATH"] = str(self.bin)

        result = subprocess.run(
            [
                sys.executable,
                str(EXTRACT_FRAMES),
                str(self.video),
                str(self.out),
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffmpeg wrote no frame", result.stderr)
        self.assertNotIn("kept ", result.stdout)
        self.assertEqual(list(self.out.glob("frame_*.jpg")), [])


if __name__ == "__main__":
    unittest.main()
