"""Tests for keepout-zone routing feature (issue #27)."""

import os
import re
import subprocess
import sys
import tempfile

import pytest

import kicad_parser as kp
from bresenham_utils import walk_line
from obstacle_map import _polygon_grid_cells
from routing_config import GridCoord
from tests.conftest import KICAD_FILES, ROOT_DIR

BASE_BOARD = str(KICAD_FILES / "flat_hierarchy.kicad_pcb")
LVDS_BOARD = str(KICAD_FILES / "lvds_converter_dualclk.kicad_pcb")
GEOM = [
    "--track-width",
    "0.5",
    "--clearance",
    "0.4",
    "--via-size",
    "0.6",
    "--via-drill",
    "0.5",
    "--layers",
    "F.Cu",
    "B.Cu",
]
CLEARANCE = "0.4"

_UUID = 0


def _gr_poly(points):
    """A closed gr_poly on User.2 from a list of (x, y) mm vertices."""
    global _UUID
    _UUID += 1
    pts = " ".join(f"(xy {x} {y})" for x, y in points)
    return (
        f"  (gr_poly (pts {pts}) (stroke (width 0.1) (type solid)) (fill none) "
        f'(layer "User.2") '
        f"(uuid 0000{_UUID:04d}-0000-0000-0000-000000000000))\n"
    )


def box(x1, y1, x2, y2):
    """Rectangle polygon (4 vertices) from opposite corners."""
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def make_board_with_keepout(polys):
    """Write a temp board = base board + the given User.2 keepout polygons."""
    text = open(BASE_BOARD).read()
    blob = "\n" + "".join(_gr_poly(p) for p in polys) + "\n"
    idx = text.rstrip().rfind(")")
    fd, path = tempfile.mkstemp(suffix=".kicad_pcb", prefix="keepout_test_")
    os.close(fd)
    with open(path, "w") as f:
        f.write(text[:idx] + blob + text[idx:])
    return path


def run_route(board_in, board_out, nets, keepout=False, verbose=False, geom=None):
    """Run route.py; return (ok, combined_output)."""
    cmd = [sys.executable, "route.py", board_in, board_out] + (geom or GEOM) + ["--nets"] + nets
    if keepout:
        cmd.append("--keepout")
    if verbose:
        cmd.append("-v")
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return (r.returncode == 0), (r.stdout + r.stderr)


def is_connected(board, nets):
    """True if check_connected reports all given nets fully connected."""
    cmd = [sys.executable, "check_connected.py", board, "--nets"] + nets
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return "ALL NETS FULLY CONNECTED" in (r.stdout + r.stderr)


def drc_counts(board, clearance=CLEARANCE):
    """Return (real_violations, same_net_crossings)."""
    cmd = [sys.executable, "check_drc.py", board, "--clearance", str(clearance)]
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if "NO DRC VIOLATIONS" in out:
        return 0, 0
    total = re.search(r"FOUND (\d+) DRC", out)
    total = int(total.group(1)) if total else -1
    selfx = re.search(r"SEGMENT-CROSSING-SAME-NET violations \((\d+)\)", out)
    selfx = int(selfx.group(1)) if selfx else 0
    return (total - selfx if total >= 0 else -1), selfx


def net_id_for(pcb, name):
    for nid, net in pcb.nets.items():
        if net.name == name:
            return nid
    return None


def net_xy_cells(board, name, grid_step=0.1):
    """Set of (gx, gy) cells occupied by a net's segments."""
    pcb = kp.parse_kicad_pcb(board)
    nid = net_id_for(pcb, name)
    coord = GridCoord(grid_step)
    cells = set()
    for s in pcb.segments:
        if s.net_id != nid:
            continue
        g1 = coord.to_grid(s.start_x, s.start_y)
        g2 = coord.to_grid(s.end_x, s.end_y)
        for gx, gy in walk_line(g1[0], g1[1], g2[0], g2[1]):
            cells.add((gx, gy))
    return cells


def keepout_cells(polys, grid_step=0.1):
    """All grid (gx, gy) cells inside any keepout polygon."""
    coord = GridCoord(grid_step)
    cells = set()
    for p in polys:
        cells |= _polygon_grid_cells(p, coord)
    return cells


def intrusions(board, name, polys, grid_step=0.1):
    """How many of a net's routed cells fall inside the keepout polygon(s)."""
    return len(net_xy_cells(board, name, grid_step) & keepout_cells(polys, grid_step))


# Net-(D8-A): TH pads at (149.22, 77.47) and (153.67, 77.47)
# Net-(D9-A): TH pads at (149.22, 87.63) and (153.80, 87.63)
D8_BOX = box(150.6, 76.4, 152.3, 78.5)
D9_BOX = box(150.6, 86.6, 152.3, 88.7)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKeepout:
    """Keepout-zone routing tests (issue #27)."""

    def test_regression_off(self):
        """Keepout present but flag OFF -> net cuts straight through the zone."""
        polys = [D8_BOX]
        board = make_board_with_keepout(polys)
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)"], keepout=False)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)"])
        inside = intrusions(out, "Net-(D8-A)", polys)
        assert inside > 0, "Route should pass through zone when flag is off"

    def test_hard_avoid(self):
        """Keepout straddling the path forces a detour; zero cells inside, clean."""
        polys = [D8_BOX]
        board = make_board_with_keepout(polys)
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)"], keepout=True)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)"])
        inside = intrusions(out, "Net-(D8-A)", polys)
        real, _selfx = drc_counts(out)
        assert inside == 0, f"Routed cells inside zone: {inside}"
        assert real == 0, f"DRC violations: {real}"

    def test_multi_net(self):
        """Two nets routed with keepout; both connect and avoid the zone(s)."""
        polys = [D8_BOX, D9_BOX]
        board = make_board_with_keepout(polys)
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        nets = ["Net-(D8-A)", "Net-(D9-A)"]
        ok, _ = run_route(board, out, nets, keepout=True)
        assert ok, "route.py failed"
        assert is_connected(out, nets)
        in8 = intrusions(out, "Net-(D8-A)", polys)
        in9 = intrusions(out, "Net-(D9-A)", polys)
        real, _selfx = drc_counts(out)
        assert in8 == 0, f"D8 cells inside zone: {in8}"
        assert in9 == 0, f"D9 cells inside zone: {in9}"
        assert real == 0, f"DRC violations: {real}"

    @pytest.mark.skipif(
        not (KICAD_FILES / "lvds_converter_dualclk.kicad_pcb").exists(),
        reason="Board not present: lvds_converter_dualclk.kicad_pcb",
    )
    def test_real_board(self):
        """Real board /CLK avoids a User.2 keepout across its path."""
        polys = [box(112.5, 64.5, 116.0, 68.0)]
        geom = ["--track-width", "0.2", "--clearance", "0.2", "--layers", "F.Cu", "B.Cu"]
        text = open(LVDS_BOARD).read()
        blob = "\n" + "".join(_gr_poly(p) for p in polys) + "\n"
        idx = text.rstrip().rfind(")")
        fd, board = tempfile.mkstemp(suffix=".kicad_pcb", prefix="keepout_lvds_")
        os.close(fd)
        with open(board, "w") as f:
            f.write(text[:idx] + blob + text[idx:])
        out = os.path.join(tempfile.gettempdir(), "lvds_clk_keepout.kicad_pcb")
        ok, _ = run_route(board, out, ["/CLK"], keepout=True, geom=geom)
        assert ok and os.path.exists(out), "route.py failed"
        assert is_connected(out, ["/CLK"])
        inside = intrusions(out, "/CLK", polys)
        real, _selfx = drc_counts(out, clearance="0.2")
        assert inside == 0, f"Routed cells inside zone: {inside}"
        assert real == 0, f"DRC violations: {real}"
