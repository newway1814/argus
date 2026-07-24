import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT_FRAMES = ROOT / "skills" / "argus" / "extract_frames.py"
CLEAN_TRANSCRIPT = ROOT / "skills" / "argus" / "clean_transcript.py"


def seconds_from_frame_name(name):
    match = re.fullmatch(r"frame_(\d+)m(\d{2})(?:\.(\d{3}))?s\.jpg", name)
    if not match:
        raise AssertionError(f"unexpected frame filename: {name}")
    minutes, seconds, millis = match.groups()
    return int(minutes) * 60 + int(seconds) + int(millis or 0) / 1000


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "ffmpeg and ffprobe are required for generated-media tests",
)
class TimeWindowCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / "scenes.mp4"
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=96x64:d=4:r=2",
                "-f",
                "lavfi",
                "-i",
                "color=c=white:s=96x64:d=4:r=2",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=96x64:d=4:r=2",
                "-filter_complex",
                "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]",
                "-map",
                "[v]",
                "-c:v",
                "mpeg4",
                cls.video,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.long_video = cls.root / "long-scenes.mp4"
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=32x32:d=100:r=1",
                "-f",
                "lavfi",
                "-i",
                "color=c=white:s=32x32:d=100:r=1",
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
                "-map",
                "[v]",
                "-c:v",
                "mpeg4",
                cls.long_video,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.captions = cls.root / "captions.vtt"
        cls.captions.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:02.000\noutside before\n\n"
            "00:00:04.000 --> 00:00:05.000\ninside first\n\n"
            "00:00:08.000 --> 00:00:09.000\ninside second\n\n"
            "00:00:10.000 --> 00:00:11.000\noutside after\n",
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_frames(self, *arguments, video=None):
        output = self.root / uuid.uuid4().hex
        return subprocess.run(
            [
                sys.executable,
                str(EXTRACT_FRAMES),
                str(video or self.video),
                str(output),
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
        ), output

    def run_transcript(self, *arguments):
        output = self.root / f"{uuid.uuid4().hex}.txt"
        return subprocess.run(
            [
                sys.executable,
                str(CLEAN_TRANSCRIPT),
                str(self.captions),
                str(output),
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
        ), output

    def test_frame_window_keeps_original_timestamps(self):
        result, output = self.run_frames("--start", "3", "--end", "9", "--min", "1")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("scene-scored", result.stdout)
        frame_names = sorted(path.name for path in output.glob("frame_*.jpg"))
        self.assertIn("frame_0m04s.jpg", frame_names)
        self.assertIn("frame_0m08s.jpg", frame_names)
        self.assertTrue(
            all(3 <= seconds_from_frame_name(name) < 9 for name in frame_names)
        )

    def test_transcript_window_keeps_original_timestamps(self):
        result, output = self.run_transcript("--start", "3", "--end", "9")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "[0:04] inside first\n[0:08] inside second",
        )

    def test_fallback_sampling_stays_inside_the_window(self):
        result, output = self.run_frames("--start", "3", "--end", "9", "--min", "99")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("even-spaced fallback", result.stdout)
        frame_names = sorted(path.name for path in output.glob("frame_*.jpg"))
        self.assertNotEqual(frame_names, [])
        self.assertTrue(
            all(3 <= seconds_from_frame_name(name) < 9 for name in frame_names)
        )

    def test_fractional_window_never_samples_before_start(self):
        result, output = self.run_frames(
            "--start",
            "3.5",
            "--end",
            "5.5",
            "--min",
            "99",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        frame_names = sorted(path.name for path in output.glob("frame_*.jpg"))
        self.assertNotEqual(frame_names, [])
        self.assertTrue(
            all(3.5 <= seconds_from_frame_name(name) < 5.5 for name in frame_names)
        )

    def test_gap_reporting_uses_window_edges(self):
        result, output = self.run_frames(
            "--start",
            "50",
            "--end",
            "180",
            "--min",
            "1",
            video=self.long_video,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(list(output.glob("frame_*.jpg")), [])
        self.assertIn("gap 1:40 -> 3:00 (80s)", result.stdout)
        self.assertNotIn("gap 0:00", result.stdout)

    def test_invalid_frame_windows_fail_without_output(self):
        cases = [
            ("--start", "-1", "--end", "9"),
            ("--start", "9", "--end", "9"),
            ("--start", "8", "--end", "7"),
            ("--start", "3", "--end", "13"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, output = self.run_frames(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_invalid_transcript_windows_fail_without_output(self):
        cases = [
            ("--start", "-1", "--end", "9"),
            ("--start", "9", "--end", "9"),
            ("--start", "8", "--end", "7"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, output = self.run_transcript(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_transcript_dedup_starts_at_the_window_boundary(self):
        duplicate_captions = self.root / "duplicate-across-boundary.vtt"
        duplicate_captions.write_text(
            "WEBVTT\n\n"
            "00:00:02.000 --> 00:00:03.000\nrepeat me\n\n"
            "00:00:04.000 --> 00:00:05.000\nrepeat me\n",
            encoding="utf-8",
        )
        output = self.root / f"{uuid.uuid4().hex}.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(CLEAN_TRANSCRIPT),
                str(duplicate_captions),
                str(output),
                "--start",
                "3",
                "--end",
                "5",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "[0:04] repeat me")

    def test_explicit_stills_must_stay_inside_the_window(self):
        result, output = self.run_frames(
            "--start",
            "3",
            "--end",
            "9",
            "--stills",
            "2,4",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
