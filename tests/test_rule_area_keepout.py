"""Tests for KiCad keep-out rule areas (PR #25, feat/keepout-obstacles)."""

import os
import tempfile
from pathlib import Path

from test_keepout import (
    BASE_BOARD,
    D8_BOX,
    D9_BOX,
    drc_counts,
    intrusions,
    is_connected,
    run_route,
)

_Z = 0


def _keepout_zone(points, layers=("F.Cu", "B.Cu"), tracks_allowed=False, vias_allowed=False):
    """A KiCad keep-out rule-area zone over the given polygon."""
    global _Z
    _Z += 1
    layer_str = " ".join(f'"{ln}"' for ln in layers)
    pts = " ".join(f"(xy {x} {y})" for x, y in points)
    tr = "allowed" if tracks_allowed else "not_allowed"
    vi = "allowed" if vias_allowed else "not_allowed"
    return (
        f"\t(zone\n"
        f'\t\t(net 0 "")\n'
        f"\t\t(layers {layer_str})\n"
        f'\t\t(uuid "0000{_Z:04d}-0000-0000-0000-000000000000")\n'
        f"\t\t(hatch edge 0.5)\n"
        f"\t\t(keepout (tracks {tr}) (vias {vi}) (pads allowed) "
        f"(copperpour not_allowed) (footprints allowed))\n"
        f"\t\t(polygon (pts {pts}))\n"
        f"\t)\n"
    )


def make_board_with_zones(zones_text):
    """Write a temp board = base board + the given keepout zone S-expressions."""
    text = Path(BASE_BOARD).read_text()
    idx = text.rstrip().rfind(")")
    fd, path = tempfile.mkstemp(suffix=".kicad_pcb", prefix="ruleko_test_")
    os.close(fd)
    with open(path, "w") as f:
        f.write(text[:idx] + "\n" + zones_text + text[idx:])
    return path


class TestRuleAreaKeepout:
    """KiCad keep-out rule-area routing tests (PR #25)."""

    def test_avoid(self):
        """Keepout straddling the path forces a detour; zero cells inside, clean."""
        polys = [D8_BOX]
        board = make_board_with_zones(_keepout_zone(D8_BOX))
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)"], keepout=False)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)"])
        inside = intrusions(out, "Net-(D8-A)", polys)
        real, _selfx = drc_counts(out)
        assert inside == 0, f"Routed cells inside rule area: {inside}"
        assert real == 0, f"DRC violations: {real}"

    def test_multi_net(self):
        """Two nets routed with a rule area present both connect and avoid it."""
        polys = [D8_BOX, D9_BOX]
        zones = _keepout_zone(D8_BOX) + _keepout_zone(D9_BOX)
        board = make_board_with_zones(zones)
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        nets = ["Net-(D8-A)", "Net-(D9-A)"]
        ok, _ = run_route(board, out, nets, keepout=False)
        assert ok, "route.py failed"
        assert is_connected(out, nets)
        in8 = intrusions(out, "Net-(D8-A)", polys)
        in9 = intrusions(out, "Net-(D9-A)", polys)
        real, _selfx = drc_counts(out)
        assert in8 == 0, f"D8 cells inside rule area: {in8}"
        assert in9 == 0, f"D9 cells inside rule area: {in9}"
        assert real == 0, f"DRC violations: {real}"

    def test_noop_gating(self):
        """Keepout that allows tracks+vias is a no-op (route cuts straight through)."""
        polys = [D8_BOX]
        board = make_board_with_zones(_keepout_zone(D8_BOX, tracks_allowed=True, vias_allowed=True))
        out = board.replace(".kicad_pcb", "_out.kicad_pcb")
        ok, _ = run_route(board, out, ["Net-(D8-A)"], keepout=False)
        assert ok, "route.py failed"
        assert is_connected(out, ["Net-(D8-A)"])
        inside = intrusions(out, "Net-(D8-A)", polys)
        assert inside > 0, "Route should pass through (tracks+vias allowed = no-op)"
