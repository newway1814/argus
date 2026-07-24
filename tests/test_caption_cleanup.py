import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_TRANSCRIPT = ROOT / "skills" / "argus" / "clean_transcript.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CaptionCleanupCliTests(unittest.TestCase):
    def clean(self, fixture):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "transcript.txt"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEAN_TRANSCRIPT),
                    str(FIXTURES / fixture),
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            body = output.read_text(encoding="utf-8") if output.exists() else None
        return result, body

    def test_cumulative_cues_become_one_readable_passage(self):
        result, body = self.clean("cumulative.vtt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(body, "[0:00] open the menu and choose settings now")

    def test_exact_duplicate_srt_cues_are_emitted_once(self):
        result, body = self.clean("exact_duplicates.srt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(body, "[0:00] hello world")

    def test_suffix_to_prefix_overlap_is_consolidated(self):
        result, body = self.clean("partial_overlap.vtt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(body, "[0:03] the quick brown fox")

    def test_same_phrase_after_a_real_gap_survives(self):
        result, body = self.clean("repeated_after_gap.vtt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(body, "[0:00] try again\n[0:10] try again")

    def test_tags_entities_karaoke_and_multiline_text_are_cleaned(self):
        result, body = self.clean("styled_multiline.vtt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(body, "[0:05] Open the menu & choose settings")

    def test_one_word_collision_and_immediate_repeat_are_preserved(self):
        result, body = self.clean("legitimate_adjacent_repetition.vtt")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            body,
            (
                "[0:00] we selected save\n"
                "[0:01] save your work often\n"
                "[0:04] Yes.\n"
                "[0:05] Yes."
            ),
        )


if __name__ == "__main__":
    unittest.main()
