"""Shared utilities for test scripts."""

import shlex
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TESTS_DIR.parent


def run(cmd: str, unbuffered: bool = False) -> subprocess.CompletedProcess:
    """Run a command string from the project root.

    Raises subprocess.CalledProcessError if the command exits non-zero.
    """
    if unbuffered and cmd.startswith("python3 "):
        cmd = "python3 -u " + cmd[8:]
    print(f"\n>>> {cmd}")
    args = shlex.split(cmd)
    return subprocess.run(args, cwd=ROOT_DIR, check=True)
