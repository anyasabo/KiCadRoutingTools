"""Tests for guide-corridor (waypoint) routing feature (issue #7)."""

import os
import subprocess
import sys
import tempfile

import pytest

import kicad_parser as kp
from bresenham_utils import walk_line
from routing_config import GridCoord, GridRouteConfig
from single_ended_routing import build_corridor_waypoints
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


def _gr_line(x1, y1, x2, y2):
    global _UUID
    _UUID += 1
    return (
        f"  (gr_line (start {x1} {y1}) (end {x2} {y2}) "
        f'(stroke (width 0.1) (type solid)) (layer "User.1") '
        f"(uuid 0000{_UUID:04d}-0000-0000-0000-000000000000))\n"
    )


def make_board_with_guide(segments):
    """Write a temp board = base board + the given User.1 guide segments."""
    text = open(BASE_BOARD).read()
    guide = "\n" + "".join(_gr_line(*s) for s in segments) + "\n"
    idx = text.rstrip().rfind(")")
    fd, path = tempfile.mkstemp(suffix=".kicad_pcb", prefix="guide_test_")
    os.close(fd)
    with open(path, "w") as f:
        f.write(text[:idx] + guide + text[idx:])
    return path


def run_route(board_in, board_out, nets, corridor=False, verbose=False, geom=None):
    """Run route.py; return (ok, combined_output)."""
    cmd = [sys.executable, "route.py", board_in, board_out] + (geom or GEOM) + ["--nets"] + nets
    if corridor:
        cmd.append("--guide-corridor")
    if verbose:
        cmd.append("-v")
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return (r.returncode == 0), (r.stdout + r.stderr)


def _pt_seg_dist(px, py, ax, ay, bx, by):
    """Distance (mm) from point to segment."""
    import math as _m

    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return _m.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return _m.hypot(px - (ax + t * dx), py - (ay + t * dy))


def guide_vertices_followed(board, name, tol_mm=2.0):
    """Count how many User.1 guide vertices the routed net passes within tol_mm of."""
    pcb = kp.parse_kicad_pcb(board)
    nid = net_id_for(pcb, name)
    segs = [s for s in pcb.segments if s.net_id == nid]
    verts = [pt for gp in pcb.guide_paths for pt in gp.points]
    followed = 0
    for vx, vy in verts:
        if segs and min(_pt_seg_dist(vx, vy, s.start_x, s.start_y, s.end_x, s.end_y) for s in segs) <= tol_mm:
            followed += 1
    return followed, len(verts)


def is_connected(board, nets):
    """True if check_connected reports all given nets fully connected."""
    cmd = [sys.executable, "check_connected.py", board, "--nets"] + nets
    r = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    return "ALL NETS FULLY CONNECTED" in (r.stdout + r.stderr)


def drc_counts(board, clearance=CLEARANCE):
    """Return (real_violations, same_net_crossings)."""
    import re

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


def net_y_extent(board, name):
    """(min_y, max_y) over the routed segments of a net."""
    pcb = kp.parse_kicad_pcb(board)
    nid = net_id_for(pcb, name)
    ys = [s.start_y for s in pcb.segments if s.net_id == nid]
    ys += [s.end_y for s in pcb.segments if s.net_id == nid]
    return (min(ys), max(ys)) if ys else (None, None)


def net_via_count(board, name):
    """Number of vias on a net."""
    pcb = kp.parse_kicad_pcb(board)
    nid = net_id_for(pcb, name)
    return sum(1 for v in pcb.vias if v.net_id == nid)


def net_occupied_cells(board, name, grid_step=0.1):
    """Set of (gx, gy, layer) cells occupied by a net's segments."""
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
            cells.add((gx, gy, s.layer))
    return cells


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGuideCorridor:
    """Guide-corridor (waypoint) routing tests (issue #7)."""

    def test_regression_off(self):
        """Guide present but flag OFF -> normal (straight) route, unchanged."""
        board = make_board_with_guide([(118.1, 57.1, 122.0, 67.0), (122.0, 67.0, 125.7, 62.2)])
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D10-A)"], corridor=False)
        assert ok, "route.py failed"
        assert os.path.exists(out)
        _, max_y = net_y_extent(out, "Net-(D10-A)")
        assert is_connected(out, ["Net-(D10-A)"])
        assert max_y is not None and max_y < 63.0, f"Route should not follow arch (max_y={max_y})"

    def test_follow(self):
        """Single net follows an arch drawn over it; connected + DRC clean."""
        board = make_board_with_guide([(118.1, 57.1, 122.0, 67.0), (122.0, 67.0, 125.7, 62.2)])
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D10-A)"], corridor=True)
        assert ok, "route.py failed"
        _, max_y = net_y_extent(out, "Net-(D10-A)")
        assert is_connected(out, ["Net-(D10-A)"])
        real, _selfx = drc_counts(out)
        assert max_y is not None and max_y >= 65.0, f"Route should follow arch (max_y={max_y})"
        assert real == 0, f"DRC violations: {real}"

    def test_blocked_waypoint(self):
        """Guide vertex on another net's through-hole pad is snapped; clean."""
        board = make_board_with_guide([(153.67, 77.47, 149.22, 83.82), (149.22, 83.82, 149.22, 77.47)])
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)"], corridor=True)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)"])
        real, _selfx = drc_counts(out)
        assert real == 0, f"DRC violations (clip of blocking pad): {real}"

    def test_shared_corridor(self):
        """Two nets follow the same arch; both connect and do not overlap."""
        board = make_board_with_guide([(153.67, 77.47, 151.4, 72.0), (151.4, 72.0, 149.22, 77.47)])
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)", "Net-(D9-A)"], corridor=True)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)", "Net-(D9-A)"])
        cells_a = net_occupied_cells(out, "Net-(D8-A)")
        cells_b = net_occupied_cells(out, "Net-(D9-A)")
        overlap = cells_a & cells_b
        assert len(overlap) == 0, f"Overlapping copper cells: {len(overlap)}"

    def test_never_blocks(self):
        """Pathological guide (off-board vertex) must not prevent routing."""
        board = make_board_with_guide([(118.1, 57.1, 10.0, 10.0), (10.0, 10.0, 125.7, 62.2)])
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D10-A)"], corridor=True)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D10-A)"])
        real, _selfx = drc_counts(out)
        assert real == 0, f"DRC violations: {real}"

    @pytest.mark.skipif(
        not (KICAD_FILES / "lvds_converter_dualclk.kicad_pcb").exists(),
        reason="Board not present: lvds_converter_dualclk.kicad_pcb",
    )
    def test_real_board(self):
        """Real board: /CLK follows its User.1 guide across the MST."""
        out = os.path.join(tempfile.gettempdir(), "lvds_clk_corridor.kicad_pcb")
        base = os.path.join(tempfile.gettempdir(), "lvds_clk_direct.kicad_pcb")
        geom = ["--track-width", "0.2", "--clearance", "0.2", "--layers", "F.Cu", "B.Cu"]
        ok, _ = run_route(LVDS_BOARD, out, ["/CLK"], corridor=True, geom=geom)
        ok_base, _ = run_route(LVDS_BOARD, base, ["/CLK"], corridor=False, geom=geom)
        assert ok and os.path.exists(out), "route.py failed"
        assert is_connected(out, ["/CLK"])
        corr_vias = net_via_count(out, "/CLK")
        direct_vias = net_via_count(base, "/CLK") if ok_base and os.path.exists(base) else 0
        real, _selfx = drc_counts(out, clearance="0.2")
        followed, total = guide_vertices_followed(out, "/CLK", tol_mm=2.0)
        assert real == 0, f"DRC violations: {real}"
        assert followed >= max(2, total - 1), f"Guide vertices followed: {followed}/{total}"
        assert corr_vias <= direct_vias, f"Corridor added vias: {corr_vias} > direct {direct_vias}"

    @pytest.mark.skipif(
        not (KICAD_FILES / "lvds_converter_dualclk.kicad_pcb").exists(),
        reason="Board not present: lvds_converter_dualclk.kicad_pcb",
    )
    def test_spacing_subdivides(self):
        """guide_corridor_spacing > 0 subdivides long guide segments (unit test)."""
        pcb = kp.parse_kicad_pcb(LVDS_BOARD)
        grid_step, spacing_mm = 0.1, 1.0
        cfg0 = GridRouteConfig(
            guide_corridor_enabled=True, guide_corridor_spacing=0.0, grid_step=grid_step, layers=["F.Cu", "B.Cu"]
        )
        cfg1 = GridRouteConfig(
            guide_corridor_enabled=True, guide_corridor_spacing=spacing_mm, grid_step=grid_step, layers=["F.Cu", "B.Cu"]
        )
        wp0 = build_corridor_waypoints(pcb, cfg0)
        wp1 = build_corridor_waypoints(pcb, cfg1)
        spacing_grid = int(spacing_mm / grid_step)
        gaps = [max(abs(wp1[i + 1][0] - wp1[i][0]), abs(wp1[i + 1][1] - wp1[i][1])) for i in range(len(wp1) - 1)]
        max_gap = max(gaps) if gaps else 0
        assert len(wp1) > len(wp0), f"Subdivision didn't add waypoints: {len(wp1)} <= {len(wp0)}"
        assert max_gap <= spacing_grid + 2, f"Max gap {max_gap} exceeds spacing {spacing_grid}+2"

    @pytest.mark.skipif(
        not (KICAD_FILES / "lvds_converter_dualclk.kicad_pcb").exists(),
        reason="Board not present: lvds_converter_dualclk.kicad_pcb",
    )
    def test_real_board_spacing(self):
        """/CLK with spacing>0 still routes cleanly and follows the guide."""
        base_geom = ["--track-width", "0.2", "--clearance", "0.2", "--layers", "F.Cu", "B.Cu"]
        out = os.path.join(tempfile.gettempdir(), "lvds_clk_spacing.kicad_pcb")
        base = os.path.join(tempfile.gettempdir(), "lvds_clk_direct2.kicad_pcb")
        ok, _ = run_route(
            LVDS_BOARD, out, ["/CLK"], corridor=True, geom=base_geom + ["--guide-corridor-spacing", "1.0"]
        )
        ok_base, _ = run_route(LVDS_BOARD, base, ["/CLK"], corridor=False, geom=base_geom)
        assert ok and os.path.exists(out), "route.py failed"
        assert is_connected(out, ["/CLK"])
        real, _selfx = drc_counts(out, clearance="0.2")
        corr_vias = net_via_count(out, "/CLK")
        direct_vias = net_via_count(base, "/CLK") if ok_base and os.path.exists(base) else 0
        followed, total = guide_vertices_followed(out, "/CLK", tol_mm=2.0)
        assert real == 0, f"DRC violations: {real}"
        assert followed >= max(2, total - 1), f"Guide vertices followed: {followed}/{total}"
        assert corr_vias <= direct_vias, f"Corridor added vias: {corr_vias} > direct {direct_vias}"
