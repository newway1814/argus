import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT_FRAMES = ROOT / "skills" / "argus" / "extract_frames.py"
CLEAN_TRANSCRIPT = ROOT / "skills" / "argus" / "clean_transcript.py"
MEDIA_AVAILABLE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
MEDIA_REQUIRED = unittest.skipUnless(
    MEDIA_AVAILABLE,
    "ffmpeg and ffprobe are required for generated-media tests",
)


def seconds_from_frame_name(name):
    match = re.fullmatch(r"frame_(\d+)m(\d{2})(?:\.(\d{3}))?s\.jpg", name)
    if not match:
        raise AssertionError(f"unexpected frame filename: {name}")
    minutes, seconds, millis = match.groups()
    return int(minutes) * 60 + int(seconds) + int(millis or 0) / 1000


class TimeWindowCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.captions = cls.root / "captions.vtt"
        cls.captions.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:02.000\noutside before\n\n"
            "00:00:04.000 --> 00:00:05.000\ninside first\n\n"
            "00:00:08.000 --> 00:00:09.000\ninside second\n\n"
            "00:00:10.000 --> 00:00:11.000\noutside after\n",
            encoding="utf-8",
        )
        if not MEDIA_AVAILABLE:
            return

        cls.video = cls.root / "scenes.mp4"
        cls.make_video(
            cls.video,
            [
                "color=c=red:s=96x64:d=4:r=2",
                "color=c=white:s=96x64:d=4:r=2",
                "color=c=black:s=96x64:d=4:r=2",
            ],
        )
        cls.long_video = cls.root / "long-scenes.mp4"
        cls.make_video(
            cls.long_video,
            [
                "color=c=black:s=32x32:d=100:r=1",
                "color=c=white:s=32x32:d=100:r=1",
            ],
        )

    @classmethod
    def make_video(cls, path, sources):
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for source in sources:
            command.extend(["-f", "lavfi", "-i", source])
        inputs = "".join(f"[{index}:v]" for index in range(len(sources)))
        command.extend(
            [
                "-filter_complex",
                f"{inputs}concat=n={len(sources)}:v=1:a=0,format=yuv420p[v]",
                "-map",
                "[v]",
                "-c:v",
                "mpeg4",
                path,
            ]
        )
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)

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

    def run_transcript(self, *arguments, captions=None):
        output = self.root / f"{uuid.uuid4().hex}.txt"
        return subprocess.run(
            [
                sys.executable,
                str(CLEAN_TRANSCRIPT),
                str(captions or self.captions),
                str(output),
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
        ), output

    @MEDIA_REQUIRED
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
        result, output = self.run_transcript(
            "--start", "3", "--end", "9", "--duration", "12"
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            output.read_text(encoding="utf-8"),
            "[0:04] inside first\n[0:08] inside second",
        )

    @MEDIA_REQUIRED
    def test_fallback_sampling_stays_inside_the_window(self):
        result, output = self.run_frames("--start", "3", "--end", "9", "--min", "99")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("even-spaced fallback", result.stdout)
        frame_names = sorted(path.name for path in output.glob("frame_*.jpg"))
        self.assertNotEqual(frame_names, [])
        self.assertTrue(
            all(3 <= seconds_from_frame_name(name) < 9 for name in frame_names)
        )

    @MEDIA_REQUIRED
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

    @MEDIA_REQUIRED
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

    @MEDIA_REQUIRED
    def test_invalid_frame_windows_fail_without_output(self):
        cases = [
            ("--start", "-1", "--end", "9"),
            ("--start", "9", "--end", "9"),
            ("--start", "8", "--end", "7"),
            ("--start", "3", "--end", "13"),
            ("--start", "nan", "--end", "9"),
            ("--start", "3", "--end", "inf"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, output = self.run_frames(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_invalid_transcript_windows_fail_without_output(self):
        cases = [
            ("--start", "-1", "--end", "9", "--duration", "12"),
            ("--start", "9", "--end", "9", "--duration", "12"),
            ("--start", "8", "--end", "7", "--duration", "12"),
            ("--start", "3", "--end", "13", "--duration", "12"),
            ("--start", "nan", "--end", "9", "--duration", "12"),
            ("--start", "3", "--end", "inf", "--duration", "12"),
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result, output = self.run_transcript(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_transcript_end_requires_source_duration(self):
        result, output = self.run_transcript("--start", "3", "--end", "9")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--duration is required", result.stderr)
        self.assertFalse(output.exists())

    def test_fractional_transcript_boundaries_are_exact(self):
        fractional = self.root / "fractional.vtt"
        fractional.write_text(
            "WEBVTT\n\n"
            "00:00:07.900 --> 00:00:08.000\ninside\n\n"
            "00:00:08.900 --> 00:00:09.000\noutside\n",
            encoding="utf-8",
        )
        result, output = self.run_transcript(
            "--start",
            "7.5",
            "--end",
            "8.5",
            "--duration",
            "12",
            captions=fractional,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "[0:07.900] inside")

    def test_transcript_dedup_starts_at_the_window_boundary(self):
        duplicate_captions = self.root / "duplicate-across-boundary.vtt"
        duplicate_captions.write_text(
            "WEBVTT\n\n"
            "00:00:02.000 --> 00:00:03.000\nrepeat me\n\n"
            "00:00:04.000 --> 00:00:05.000\nrepeat me\n",
            encoding="utf-8",
        )
        result, output = self.run_transcript(
            "--start",
            "3",
            "--end",
            "5",
            "--duration",
            "6",
            captions=duplicate_captions,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "[0:04] repeat me")

    @MEDIA_REQUIRED
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
