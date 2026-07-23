"""Read-only preflight for the Argus runtime and configured capabilities."""

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 9)
DEFAULT_MODEL = "small"
SYNC_FOLDERS = {"onedrive", "dropbox", "google drive", "icloud drive"}


def platform_name(requested):
    if requested != "auto":
        return requested
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    return "linux"


def command_parts(value, platform):
    text = str(value or "").strip()
    if not text:
        return []
    path = Path(text).expanduser()
    if path.is_absolute() and path.exists():
        return [str(path)]
    return shlex.split(text, posix=platform != "windows")


def python_probe_source(model):
    model_folder = json.dumps(
        f"models--Systran--faster-whisper-{model}"
    )
    return f"""
import importlib.util
import json
import os
import sys
from pathlib import Path

cache_root = Path(
    os.environ.get("HF_HUB_CACHE")
    or os.environ.get("HUGGINGFACE_HUB_CACHE")
    or Path.home() / ".cache" / "huggingface" / "hub"
)
model_dir = cache_root / {model_folder}
snapshots = model_dir / "snapshots"
cached = snapshots.is_dir() and any(path.is_file() for path in snapshots.rglob("*"))
print(json.dumps({{
    "sys_executable": sys.executable,
    "version": list(sys.version_info[:3]),
    "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
    "model_cached": cached,
}}))
"""


def probe_python(parts, model):
    if not parts:
        return None, "python_cmd is empty"
    try:
        result = subprocess.run(
            [*parts, "-c", python_probe_source(model)],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "probe failed"
        return None, detail
    try:
        return json.loads(result.stdout.strip().splitlines()[-1]), None
    except (IndexError, json.JSONDecodeError):
        return None, "probe returned no readable result"


def probe_command(name, version_args):
    path = shutil.which(name)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *version_args],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    first_line = (result.stdout or result.stderr).strip().splitlines()
    return (path, first_line[0] if first_line else "version unknown")


def config_is_secure(path, platform):
    if platform == "windows":
        try:
            relative = path.resolve().relative_to(Path.home().resolve())
        except ValueError:
            return False
        lowered = {part.lower() for part in relative.parts}
        return not lowered.intersection(SYNC_FOLDERS)
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def vault_is_writable(path):
    if not path.is_dir():
        return False
    mode = stat.S_IMODE(path.stat().st_mode)
    return bool(mode & stat.S_IWUSR) and os.access(path, os.W_OK)


def status(ready):
    return "ready" if ready else "unavailable"


def vault_preparation_command(path, platform):
    if platform == "windows":
        return f'icacls "{path}" /grant "%USERNAME%:(OI)(CI)M"'
    return f'chmod u+w "{path}"'


def config_preparation_command(path, platform):
    if platform == "windows":
        destination = "$HOME\\.claude\\argus.config.json"
        return (
            f'Move-Item -LiteralPath "{path}" -Destination "{destination}"'
        )
    return f'chmod 600 "{path}"'


def tool_preparation_command(capability, platform):
    commands = {
        "node": {
            "macos": "brew install node",
            "linux": "sudo apt-get install -y nodejs",
            "windows": "winget install --id OpenJS.NodeJS.LTS --exact",
        },
        "frames": {
            "macos": "brew install ffmpeg",
            "linux": "sudo apt-get install -y ffmpeg",
            "windows": "winget install --id Gyan.FFmpeg --exact",
        },
    }
    return commands[capability][platform]


def python_preparation_command(platform):
    return {
        "macos": "brew install python@3.12",
        "linux": "sudo apt-get install -y python3",
        "windows": "winget install --id Python.Python.3.12 --exact",
    }[platform]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".claude" / "argus.config.json",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "macos", "linux", "windows"),
        default="auto",
        help="override operating-system command guidance",
    )
    parser.add_argument(
        "--python",
        dest="python_override",
        help="probe this candidate without writing it to config",
    )
    args = parser.parse_args()
    platform = platform_name(args.platform)
    config_path = args.config.expanduser()

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"config: unavailable ({error})")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1
    if not isinstance(config, dict):
        print("config: expected a JSON object")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1

    model = str(config.get("transcription_model") or DEFAULT_MODEL)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", model):
        print("config: transcription_model is invalid")
        print("  prepare: /argus setup")
        print("overall: unhealthy")
        return 1
    configured_python = str(
        args.python_override or config.get("python_cmd") or ""
    )
    python_info, python_error = probe_python(
        command_parts(configured_python, platform),
        model,
    )
    python_ready = bool(
        python_info
        and tuple(python_info.get("version", (0, 0))) >= MINIMUM_PYTHON
    )
    faster_whisper = bool(python_info and python_info.get("faster_whisper"))
    model_cached = bool(python_info and python_info.get("model_cached"))

    tools = {
        "yt-dlp": probe_command("yt-dlp", ("--version",)),
        "node": probe_command("node", ("--version",)),
        "ffmpeg": probe_command("ffmpeg", ("-version",)),
        "ffprobe": probe_command("ffprobe", ("-version",)),
    }
    config_secure = config_is_secure(config_path, platform)
    vault_path = Path(str(config.get("vault_path") or "")).expanduser()
    vault_writable = vault_is_writable(vault_path)

    captions = python_ready and bool(tools["yt-dlp"])
    transcription = python_ready and faster_whisper and model_cached
    frames = bool(tools["ffmpeg"] and tools["ffprobe"])
    vault_writing = python_ready and config_secure and vault_writable
    intake_configured = bool(
        config.get("playlist_url")
        or (config.get("telegram_token") and config.get("telegram_owner_id"))
    )
    queue = captions and vault_writing and intake_configured
    telegram = bool(
        config_secure
        and config.get("telegram_token")
        and config.get("telegram_owner_id")
    )

    print("Argus doctor (read-only)")
    print(f"platform: {platform}")
    print(f"config: {config_path}")
    print(f"config permissions: {status(config_secure)}")
    if not config_secure:
        print(
            f"  prepare: {config_preparation_command(config_path, platform)}"
        )
    print("Python")
    print(f"  configured: {configured_python or 'missing'}")
    if python_info:
        version = ".".join(str(part) for part in python_info["version"])
        print(f"  resolved: {python_info['sys_executable']}")
        print(f"  version: {version}")
        if tuple(python_info["version"]) < MINIMUM_PYTHON:
            print(f"    prepare: {python_preparation_command(platform)}")
        print(f"  faster-whisper: {status(faster_whisper)}")
        if not faster_whisper:
            print(
                f'    prepare: "{python_info["sys_executable"]}" '
                "-m pip install faster-whisper"
            )
        print(f"  model {model} cache: {status(model_cached)}")
        if faster_whisper and not model_cached:
            prefetch = Path(__file__).with_name("transcribe_audio.py")
            print(
                f'    prepare: "{python_info["sys_executable"]}" '
                f'"{prefetch}" --prefetch'
            )
    else:
        print("  resolved: unavailable")
        print(f"  error: {python_error}")
        print("    prepare: /argus setup")
    print("Tools")
    for name, result in tools.items():
        if result:
            print(f"  {name}: ready ({result[1]})")
        else:
            print(f"  {name}: unavailable")
            if name == "yt-dlp" and python_info:
                resolved = python_info["sys_executable"]
                print(
                    f'    prepare: "{resolved}" -m pip install --upgrade yt-dlp'
                )
            if name == "node":
                command = tool_preparation_command("node", platform)
                print(f"    prepare: {command}")
    if not frames:
        command = tool_preparation_command("frames", platform)
        print(f"  frame tools prepare: {command}")
    print(f"vault: {vault_path}")
    if not vault_writable:
        print(f"  prepare: {vault_preparation_command(vault_path, platform)}")
    print("Capabilities")
    print(f"  captions: {status(captions)}")
    print(f"  transcription: {status(transcription)}")
    print(f"  frames: {status(frames)}")
    print(f"  vault writing: {status(vault_writing)}")
    print(f"  queue: {status(queue)}")
    print(f"  Telegram: {status(telegram)}")

    required_healthy = python_ready and bool(tools["yt-dlp"]) and vault_writing
    print(f"overall: {'healthy' if required_healthy else 'unhealthy'}")
    return 0 if required_healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
