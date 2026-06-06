"""Shared pytest configuration, fixtures, and markers for KiCadRoutingTools tests."""

import shlex
import subprocess
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
KICAD_FILES = ROOT_DIR / "kicad_files"

SLOW_MODULES = {
    "test_fanout_and_route",
    "test_kit_route",
    "test_flat_hierarchy",
    "test_interf_u",
    "test_sonde_u",
}


def run_tool(cmd: str | list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a project tool from the project root.

    Args:
        cmd: Command string (shlex-split) or list.
        check: If True, raise CalledProcessError on non-zero exit.
    """
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = list(cmd)

    return subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True, check=check)


def requires_board(board_path: str | Path):
    """Skip decorator for tests that need a specific board file."""
    path = Path(board_path)
    return pytest.mark.skipif(not path.exists(), reason=f"Board not present: {path.name}")


def pytest_addoption(parser):
    parser.addoption("--quick", action="store_true", default=False, help="Run pipeline tests in quick mode")


@pytest.fixture
def quick(request):
    return request.config.getoption("--quick")


def pytest_collection_modifyitems(config, items):
    """Auto-add 'slow' marker to pipeline test modules."""
    for item in items:
        if item.module and item.module.__name__.split(".")[-1] in SLOW_MODULES:
            item.add_marker(pytest.mark.slow)
