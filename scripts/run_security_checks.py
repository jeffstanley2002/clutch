"""Run secret and dependency checks used locally and in CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPOSITORY_ROOT / ".secrets.baseline"


def _repository_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    paths = result.stdout.decode("utf-8").split("\0")
    return [path for path in paths if path and path != BASELINE_PATH.name]


def _detect_secrets_hook() -> Path:
    hook = Path(sys.executable).with_name("detect-secrets-hook")
    if not hook.is_file():
        raise RuntimeError(
            "detect-secrets-hook is missing; install the project with .[dev]"
        )
    return hook


def main() -> None:
    """Fail if tracked/new files contain a secret or dependencies are unsafe."""

    files = _repository_files()
    secret_command = (
        str(_detect_secrets_hook()),
        "--baseline",
        str(BASELINE_PATH),
        *files,
    )
    audit_command = (
        sys.executable,
        "-m",
        "pip_audit",
        ".",
        "--strict",
        "--progress-spinner",
        "off",
    )
    for command in (secret_command, audit_command):
        print(f"\n$ {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


if __name__ == "__main__":
    main()
