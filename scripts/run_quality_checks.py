"""Run the deterministic quality gates used locally and in CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    (sys.executable, "-m", "ruff", "check", "."),
    (
        sys.executable,
        "-m",
        "mypy",
        "src",
        "backend",
        "frontend",
        "scripts",
    ),
    (sys.executable, "-m", "pytest", "-q"),
    (sys.executable, "-m", "clutch.evals.runner", "--compact"),
)


def main() -> None:
    """Fail fast when any required quality command returns non-zero."""

    for command in COMMANDS:
        print(f"\n$ {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


if __name__ == "__main__":
    main()
