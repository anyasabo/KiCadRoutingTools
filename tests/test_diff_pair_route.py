"""Differential-pair routing correctness tests."""

import os
import subprocess
import sys

import pytest

from tests.conftest import KICAD_FILES, ROOT_DIR

BOARD = str(KICAD_FILES / "routed_output.kicad_pcb")
GEOM = [
    "--track-width",
    "0.1",
    "--clearance",
    "0.1",
    "--via-size",
    "0.3",
    "--via-drill",
    "0.2",
    "--layers",
    "F.Cu",
    "In1.Cu",
    "In2.Cu",
    "In3.Cu",
    "B.Cu",
    "--impedance",
    "100",
    "--proximity-heuristic-factor",
    "0.0",
]
CLEARANCE = "0.1"
PAIRS = ["lvds_rx1_11", "lvds_rx1_10", "lvds_rx1_12"]


def route_pair(pattern, out):
    """Route the single pair matching *pattern*; return (routed_ok, output)."""
    cmd = [sys.executable, "route_diff.py", BOARD, out, "--nets", f"*{pattern}*"] + GEOM
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    txt = r.stdout + r.stderr
    return ('"successful": 1' in txt and '"failed": 0' in txt), txt


def is_connected(board, pattern):
    """True if check_connected reports the pair's nets fully connected."""
    cmd = [sys.executable, "check_connected.py", board, "--nets", f"*{pattern}*"]
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return "ALL NETS FULLY CONNECTED" in (r.stdout + r.stderr)


def drc_clean(board, pattern):
    """True if the pair has no DRC violations (scoped to its own nets)."""
    cmd = [
        sys.executable,
        "check_drc.py",
        board,
        "--clearance",
        CLEARANCE,
        "--nets",
        f"*{pattern}*",
        "--clearance-margin",
        "0.1",
    ]
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return "NO DRC VIOLATIONS" in (r.stdout + r.stderr)


@pytest.mark.skipif(not os.path.exists(BOARD), reason="Board not present: routed_output.kicad_pcb")
@pytest.mark.parametrize("pattern", PAIRS)
def test_diff_pair(pattern, tmp_path):
    """Each differential pair routes connected + DRC-clean."""
    out = str(tmp_path / f"diffroute_{pattern}.kicad_pcb")
    routed, txt = route_pair(pattern, out)
    assert routed, f"route_diff did not report 1/1 routed for {pattern}"
    assert os.path.exists(out)
    assert is_connected(out, pattern), f"{pattern} not fully connected"
    assert drc_clean(out, pattern), f"{pattern} has DRC violations"
