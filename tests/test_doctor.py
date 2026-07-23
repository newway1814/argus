import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "skills" / "argus" / "doctor.py"
HOST_PLATFORM = (
    "windows"
    if os.name == "nt"
    else "macos"
    if sys.platform == "darwin"
    else "linux"
)


class DoctorCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.vault = self.root / "vault"
        self.home.mkdir()
        self.bin.mkdir()
        self.vault.mkdir()
        self.config = self.home / ".claude" / "argus.config.json"
        self.config.parent.mkdir()

    def executable(self, name, output):
        path = self.bin / (f"{name}.cmd" if os.name == "nt" else name)
        if os.name == "nt":
            path.write_text(
                f"@echo off\r\necho {output}\r\n",
                encoding="utf-8",
            )
        else:
            path.write_text(
                f"#!/bin/sh\nprintf '%s\\n' '{output}'\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    def python_executable(
        self,
        *,
        version=(3, 12, 2),
        faster_whisper=True,
        model_cached=True,
        resolved=None,
    ):
        name = "argus-python.cmd" if os.name == "nt" else "argus-python"
        path = self.bin / name
        payload = json.dumps(
            {
                "sys_executable": str(resolved or path),
                "version": list(version),
                "faster_whisper": faster_whisper,
                "model_cached": model_cached,
            }
        )
        if os.name == "nt":
            path.write_text(
                "@echo off\r\n"
                'if "%1"=="--version" (\r\n'
                f"  echo Python {version[0]}.{version[1]}.{version[2]}\r\n"
                ") else (\r\n"
                f"  echo {payload}\r\n"
                ")\r\n",
                encoding="utf-8",
            )
        else:
            path.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then\n"
                f"  printf '%s\\n' 'Python {version[0]}.{version[1]}.{version[2]}'\n"
                "else\n"
                f"  printf '%s\\n' '{payload}'\n"
                "fi\n",
                encoding="utf-8",
            )
            path.chmod(0o755)
        return path

    def secure_config(self, path):
        if os.name == "nt":
            user = os.environ["USERNAME"]
            for arguments in (
                ["/reset"],
                ["/inheritance:r"],
                ["/grant:r", f"{user}:F"],
            ):
                subprocess.run(
                    ["icacls", str(path), *arguments],
                    text=True,
                    capture_output=True,
                    check=True,
                )
        else:
            path.chmod(0o600)

    def write_config(self, python_cmd):
        self.config.write_text(
            json.dumps(
                {
                    "vault_path": str(self.vault),
                    "python_cmd": str(python_cmd),
                    "playlist_url": "https://youtube.com/playlist?list=test",
                    "telegram_token": "test-token",
                    "telegram_owner_id": 123,
                    "transcription_model": "small",
                }
            ),
            encoding="utf-8",
        )
        self.secure_config(self.config)

    def prepare_machine(
        self,
        *,
        python_cmd=None,
        python_options=None,
        yt_dlp=True,
        node=True,
        ffmpeg=True,
        ffprobe=True,
    ):
        python_cmd = python_cmd or self.python_executable(
            **(python_options or {})
        )
        self.write_config(python_cmd)
        commands = {
            "yt-dlp": (yt_dlp, "2026.07.01"),
            "node": (node, "v24.0.0"),
            "ffmpeg": (ffmpeg, "ffmpeg version 8.0"),
            "ffprobe": (ffprobe, "ffprobe version 8.0"),
        }
        for name, (enabled, output) in commands.items():
            if enabled:
                self.executable(name, output)
        return python_cmd

    def run_doctor(self, platform=HOST_PLATFORM, config=None, extra_env=None):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PATH"] = str(self.bin)
        env.update(extra_env or {})
        config = config or self.config
        return subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--config",
                str(config),
                "--platform",
                platform,
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_healthy_environment_reports_every_capability(self):
        python = self.prepare_machine()

        result = self.run_doctor()
        acl_diagnostics = ""
        if os.name == "nt":
            acl_diagnostics = subprocess.run(
                ["icacls", str(self.config)],
                text=True,
                capture_output=True,
                check=False,
            ).stdout

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr + acl_diagnostics,
        )
        self.assertIn(f"configured: {python}", result.stdout)
        self.assertIn(f"resolved: {python}", result.stdout)
        self.assertIn("captions: ready", result.stdout)
        self.assertIn("transcription: ready", result.stdout)
        self.assertIn("frames: ready", result.stdout)
        self.assertIn("vault writing: ready", result.stdout)
        self.assertIn("queue: ready", result.stdout)
        self.assertIn("Telegram: ready", result.stdout)
        self.assertIn("overall: healthy", result.stdout)

    def test_missing_required_command_fails_with_one_preparation_command_per_os(self):
        python = self.prepare_machine(yt_dlp=False)

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        command = f'"{python}" -m pip install --upgrade yt-dlp'
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
        self.assertIn("captions: unavailable", result.stdout)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_wrong_interpreter_does_not_borrow_dependencies_from_doctor_runtime(self):
        python = self.python_executable(
            faster_whisper=False,
            model_cached=False,
        )
        self.prepare_machine(python_cmd=python)

        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"configured: {python}", result.stdout)
        self.assertIn(f"resolved: {python}", result.stdout)
        self.assertIn("faster-whisper: unavailable", result.stdout)
        self.assertIn("transcription: unavailable", result.stdout)
        self.assertIn(
            "limitation: captioned videos work; reels and captionless videos",
            result.stdout,
        )
        command = f'"{python}" -m pip install faster-whisper'
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    def test_unwritable_vault_fails_with_os_specific_preparation_command(self):
        self.prepare_machine()
        self.vault.chmod(0o500)
        self.addCleanup(self.vault.chmod, 0o700)
        expected = {
            "macos": f'chmod u+w "{self.vault}"',
            "linux": f'chmod u+w "{self.vault}"',
            "windows": (
                f'icacls "{self.vault}" /grant "%USERNAME%:(OI)(CI)M"'
            ),
        }

        result = self.run_doctor()
        command = expected[HOST_PLATFORM]

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("vault writing: unavailable", result.stdout)
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_insecure_config_fails_with_os_specific_preparation_command(self):
        self.prepare_machine()

        if HOST_PLATFORM == "windows":
            outside = self.root / "OneDrive" / "argus.config.json"
            outside.parent.mkdir()
            outside.write_bytes(self.config.read_bytes())
            self.secure_config(outside)
            result = self.run_doctor(config=outside)
            destination = "$HOME\\.claude\\argus.config.json"
            command = (
                f'Move-Item -LiteralPath "{outside}" '
                f'-Destination "{destination}"'
            )
        else:
            self.config.chmod(0o644)
            result = self.run_doctor()
            command = f'chmod 600 "{self.config}"'

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config permissions: unavailable", result.stdout)
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    def test_optional_failures_print_commands_without_running_or_writing_them(self):
        python = self.prepare_machine(
            python_options={
                "faster_whisper": False,
                "model_cached": False,
            },
            node=False,
            ffmpeg=False,
            ffprobe=False,
        )
        package_manager_marker = self.root / "package-manager-ran"
        manager = {
            "macos": "brew",
            "linux": "apt-get",
            "windows": "winget",
        }[HOST_PLATFORM]
        manager_path = self.bin / (
            f"{manager}.cmd" if os.name == "nt" else manager
        )
        if os.name == "nt":
            manager_path.write_text(
                "@echo off\r\n"
                f'type nul > "{package_manager_marker}"\r\n'
                "exit /b 99\r\n",
                encoding="utf-8",
            )
        else:
            manager_path.write_text(
                "#!/bin/sh\n"
                f'touch "{package_manager_marker}"\n'
                "exit 99\n",
                encoding="utf-8",
            )
            manager_path.chmod(0o755)
        before = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mode)
            for path in self.root.rglob("*")
            if path.is_file()
        }

        result = self.run_doctor()

        after = {
            path.relative_to(self.root): (path.read_bytes(), path.stat().st_mode)
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, after)
        self.assertFalse(package_manager_marker.exists())
        node_command = {
            "macos": "brew install node",
            "linux": "sudo apt-get install -y nodejs",
            "windows": "winget install --id OpenJS.NodeJS.LTS --exact",
        }[HOST_PLATFORM]
        frame_command = {
            "macos": "brew install ffmpeg",
            "linux": "sudo apt-get install -y ffmpeg",
            "windows": "winget install --id Gyan.FFmpeg --exact",
        }[HOST_PLATFORM]
        self.assertEqual(result.stdout.count(f"prepare: {node_command}"), 1)
        self.assertEqual(result.stdout.count(f"prepare: {frame_command}"), 1)
        self.assertEqual(
            result.stdout.count(
                f'prepare: "{python}" -m pip install faster-whisper'
            ),
            1,
        )

    def test_uncached_model_reports_explicit_prefetch_without_downloading(self):
        python = self.prepare_machine(
            python_options={"model_cached": False}
        )

        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("model small cache: unavailable", result.stdout)
        self.assertIn("transcription: unavailable", result.stdout)
        prefetch = DOCTOR.with_name("transcribe_audio.py")
        command = f'"{python}" "{prefetch}" --prefetch'
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    def test_unsupported_python_version_is_a_required_failure(self):
        self.prepare_machine(
            python_options={"version": (3, 8, 19)}
        )
        expected = {
            "macos": "brew install python@3.12",
            "linux": "sudo apt-get install -y python3",
            "windows": "winget install --id Python.Python.3.12 --exact",
        }

        result = self.run_doctor()
        command = expected[HOST_PLATFORM]

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version: 3.8.19", result.stdout)
        self.assertIn("frames: unavailable", result.stdout)
        self.assertIn("Telegram: unavailable", result.stdout)
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_missing_configured_python_fails_with_setup_command(self):
        missing = self.root / "missing-python"
        self.prepare_machine(python_cmd=missing, yt_dlp=False)

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"configured: {missing}", result.stdout)
        self.assertIn("resolved: unavailable", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)
        yt_dlp_command = {
            "macos": "brew install yt-dlp",
            "linux": "sudo apt-get install -y yt-dlp",
            "windows": "winget install --id yt-dlp.yt-dlp --exact",
        }[HOST_PLATFORM]
        self.assertEqual(
            result.stdout.count(f"prepare: {yt_dlp_command}"),
            1,
        )
        self.assertIn("overall: unhealthy", result.stdout)

    def test_missing_config_file_fails_with_setup_command(self):
        missing = self.root / "missing-config.json"

        result = self.run_doctor(config=missing)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config: unavailable", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)
        self.assertIn("overall: unhealthy", result.stdout)

    def test_model_name_from_config_cannot_execute_python(self):
        marker = self.root / "model-name-executed"
        malicious_model = (
            'small"\n'
            f'Path(r"{marker}").write_text("bad")\n'
            "#"
        )
        self.config.write_text(
            json.dumps(
                {
                    "vault_path": str(self.vault),
                    "python_cmd": sys.executable,
                    "playlist_url": "https://youtube.com/playlist?list=test",
                    "telegram_token": "",
                    "telegram_owner_id": None,
                    "transcription_model": malicious_model,
                }
            ),
            encoding="utf-8",
        )
        self.secure_config(self.config)
        self.executable("yt-dlp", "2026.07.01")

        self.run_doctor()

        self.assertFalse(marker.exists())

    def test_non_object_config_reports_failure_instead_of_crashing(self):
        self.config.write_text("[]", encoding="utf-8")
        self.secure_config(self.config)

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("config: expected a JSON object", result.stdout)
        self.assertEqual(result.stdout.count("prepare: /argus setup"), 1)

    def test_nonexistent_vault_gets_a_creation_command_not_chmod(self):
        self.prepare_machine()
        missing_vault = self.root / "missing-vault"
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["vault_path"] = str(missing_vault)
        self.config.write_text(json.dumps(config), encoding="utf-8")
        self.secure_config(self.config)
        expected = {
            "macos": f'mkdir -p "{missing_vault}"',
            "linux": f'mkdir -p "{missing_vault}"',
            "windows": (
                "New-Item -ItemType Directory -Force "
                f'-Path "{missing_vault}"'
            ),
        }[HOST_PLATFORM]

        result = self.run_doctor()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count(f"prepare: {expected}"), 1)

    def test_partial_model_snapshot_is_not_reported_as_cached(self):
        cache = self.root / "huggingface"
        snapshot = (
            cache
            / "models--Systran--faster-whisper-small"
            / "snapshots"
            / "partial"
        )
        snapshot.mkdir(parents=True)
        (snapshot / "model.bin").write_bytes(b"partial")
        self.prepare_machine(
            python_cmd=sys.executable,
            node=False,
            ffmpeg=False,
            ffprobe=False,
        )

        result = self.run_doctor(
            extra_env={"HF_HUB_CACHE": str(cache)}
        )

        self.assertIn("model small cache: unavailable", result.stdout)

        (snapshot / "config.json").write_text("{}", encoding="utf-8")
        (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
        (snapshot / "model.bin").write_bytes(b"")
        zero_weight = self.run_doctor(
            extra_env={"HF_HUB_CACHE": str(cache)}
        )

        self.assertIn(
            "model small cache: unavailable",
            zero_weight.stdout,
        )

        (snapshot / "model.bin").write_bytes(b"weights")
        complete = self.run_doctor(
            extra_env={"HF_HUB_CACHE": str(cache)}
        )
        self.assertIn("model small cache: ready", complete.stdout)

    def test_broken_faster_whisper_install_is_not_reported_as_importable(self):
        site = self.root / "site"
        site.mkdir()
        (site / "faster_whisper.py").write_text(
            'raise RuntimeError("broken native dependency")\n',
            encoding="utf-8",
        )
        self.prepare_machine(
            python_cmd=sys.executable,
            node=False,
            ffmpeg=False,
            ffprobe=False,
        )

        result = self.run_doctor(extra_env={"PYTHONPATH": str(site)})

        self.assertIn("faster-whisper: unavailable", result.stdout)
        self.assertIn("broken native dependency", result.stdout)

    def test_windows_acl_readable_by_everyone_is_insecure(self):
        self.prepare_machine()
        cleanup_acl = None
        if os.name == "nt":
            subprocess.run(
                ["icacls", str(self.config), "/grant", "*S-1-1-0:(R)"],
                text=True,
                capture_output=True,
                check=True,
            )

            def cleanup_acl():
                subprocess.run(
                    [
                        "icacls",
                        str(self.config),
                        "/remove:g",
                        "*S-1-1-0",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )

            self.addCleanup(cleanup_acl)
        else:
            self.executable(
                "powershell.exe",
                "S-1-1-0|Read|Allow",
            )
        command = (
            f'icacls "{self.config}" /reset; '
            f'icacls "{self.config}" /inheritance:r; '
            f'icacls "{self.config}" /grant:r "${{env:USERNAME}}:F"'
        )

        result = self.run_doctor("windows")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config permissions: unavailable", result.stdout)
        self.assertEqual(result.stdout.count(f"prepare: {command}"), 1)

    @unittest.skipIf(os.name == "nt", "simulated ACL fixture is POSIX-only")
    def test_windows_acl_readable_by_another_account_is_insecure(self):
        self.prepare_machine()
        self.executable(
            "powershell.exe",
            "CURRENT|S-1-5-21-1000|\n"
            "S-1-5-21-1000|FullControl|Allow\n"
            "S-1-5-21-2000|Read|Allow",
        )

        result = self.run_doctor("windows")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config permissions: unavailable", result.stdout)

    def test_telegram_only_queue_requires_a_paired_owner(self):
        self.prepare_machine()
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["playlist_url"] = ""
        config["telegram_owner_id"] = None
        self.config.write_text(json.dumps(config), encoding="utf-8")
        self.secure_config(self.config)

        result = self.run_doctor()

        self.assertIn("queue: unavailable", result.stdout)
        self.assertIn("Telegram: unavailable", result.stdout)
        self.assertEqual(
            result.stdout.count("prepare: /argus setup telegram"),
            1,
        )

    def test_linux_commands_follow_detected_package_manager(self):
        self.prepare_machine(node=False, ffmpeg=False, ffprobe=False)
        self.executable("dnf", "dnf 5")

        result = self.run_doctor("linux")

        self.assertIn("prepare: sudo dnf install -y nodejs", result.stdout)
        self.assertIn(
            "prepare: sudo dnf install -y ffmpeg-free",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
