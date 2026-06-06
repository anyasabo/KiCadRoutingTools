"""Unit tests for kicad_parser.py: S-expression parsing, net extraction, version detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kicad_parser import (
    detect_kicad_version,
    extract_layers,
    extract_nets,
    extract_segments,
    extract_stackup,
    extract_vias,
    is_kicad_10,
    local_to_global,
    parse_s_expression,
)


class TestVersionDetection:
    def test_kicad_9(self):
        content = '(kicad_pcb (version 20241229) (generator "pcbnew"))'
        assert detect_kicad_version(content) == 20241229
        assert not is_kicad_10(content)

    def test_kicad_10(self):
        content = '(kicad_pcb (version 20260206) (generator "pcbnew"))'
        assert detect_kicad_version(content) == 20260206
        assert is_kicad_10(content)

    def test_missing_version(self):
        assert detect_kicad_version("(kicad_pcb)") == 0
        assert not is_kicad_10("(kicad_pcb)")


class TestSExpressionParser:
    def test_simple(self):
        result = parse_s_expression('(net 1 "GND")')
        assert result == [["net", "1", "GND"]]

    def test_nested(self):
        result = parse_s_expression("(segment (start 1.0 2.0) (end 3.0 4.0) (net 5))")
        assert result == [["segment", ["start", "1.0", "2.0"], ["end", "3.0", "4.0"], ["net", "5"]]]

    def test_empty(self):
        result = parse_s_expression("")
        assert result == []


class TestExtractNets:
    def test_kicad_9_nets(self):
        content = '(net 0 "")\n(net 1 "GND")\n(net 2 "+3V3")\n'
        nets, name_to_id = extract_nets(content, kicad_version=20241229)
        assert 1 in nets
        assert nets[1].name == "GND"
        assert nets[2].name == "+3V3"
        assert name_to_id["GND"] == 1

    def test_kicad_10_nets(self):
        content = """(kicad_pcb (version 20260206)
  (footprint "R_0402"
    (pad "1" smd roundrect (at 0 0) (size 0.5 0.6) (layers "F.Cu") (net "GND"))
    (pad "2" smd roundrect (at 1 0) (size 0.5 0.6) (layers "F.Cu") (net "+3V3"))
  )
  (segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net "GND"))
)"""
        nets, name_to_id = extract_nets(content, kicad_version=20260206)
        assert "GND" in name_to_id
        assert "+3V3" in name_to_id
        gnd_id = name_to_id["GND"]
        assert nets[gnd_id].name == "GND"


class TestExtractLayers:
    def test_basic_layers(self):
        content = """(layers
  (0 "F.Cu" signal)
  (31 "B.Cu" signal)
  (32 "B.Adhes" user)
)"""
        board_info = extract_layers(content)
        assert board_info.layers[0] == "F.Cu"
        assert board_info.layers[31] == "B.Cu"
        assert "F.Cu" in board_info.copper_layers
        assert "B.Cu" in board_info.copper_layers
        assert "B.Adhes" not in board_info.copper_layers


class TestExtractStackup:
    def test_stackup(self):
        content = """(stackup
  (layer "F.Cu" (type "copper") (thickness 0.035))
  (layer "dielectric 1" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
  (layer "B.Cu" (type "copper") (thickness 0.035))
  (copper_finish "ENIG")
)"""
        stackup = extract_stackup(content)
        assert len(stackup) == 3
        assert stackup[0].name == "F.Cu"
        assert stackup[0].layer_type == "copper"
        assert stackup[1].epsilon_r == 4.5
        assert stackup[1].material == "FR4"


class TestLocalToGlobal:
    def test_no_rotation(self):
        x, y = local_to_global(100.0, 50.0, 0.0, 1.0, 2.0)
        assert abs(x - 101.0) < 1e-6
        assert abs(y - 52.0) < 1e-6

    def test_90_degree(self):
        x, y = local_to_global(100.0, 50.0, 90.0, 1.0, 0.0)
        assert abs(x - 100.0) < 1e-6
        assert abs(y - 49.0) < 1e-6

    def test_180_degree(self):
        x, y = local_to_global(100.0, 50.0, 180.0, 1.0, 0.0)
        assert abs(x - 99.0) < 1e-6
        assert abs(y - 50.0) < 1e-6


class TestExtractVias:
    def test_kicad_9_via(self):
        content = '(via (at 100.5 50.2) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 5) (uuid "abc"))'
        vias = extract_vias(content)
        assert len(vias) == 1
        assert abs(vias[0].x - 100.5) < 1e-6
        assert abs(vias[0].y - 50.2) < 1e-6
        assert vias[0].net_id == 5

    def test_kicad_10_via(self):
        content = '(via (at 100.5 50.2) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (tenting (front yes) (back yes)) (net "GND") (uuid "abc"))'
        name_to_id = {"GND": 1}
        vias = extract_vias(content, name_to_id)
        assert len(vias) == 1
        assert vias[0].net_id == 1


class TestExtractSegments:
    def test_kicad_9_segment(self):
        content = '(segment (start 10.0 20.0) (end 30.0 40.0) (width 0.25) (layer "F.Cu") (net 3) (uuid "xyz"))'
        segs = extract_segments(content)
        assert len(segs) == 1
        assert abs(segs[0].start_x - 10.0) < 1e-6
        assert abs(segs[0].end_y - 40.0) < 1e-6
        assert segs[0].layer == "F.Cu"
        assert segs[0].net_id == 3

    def test_kicad_10_segment(self):
        content = '(segment (start 10.0 20.0) (end 30.0 40.0) (width 0.25) (layer "F.Cu") (net "SIG1") (uuid "xyz"))'
        name_to_id = {"SIG1": 7}
        segs = extract_segments(content, name_to_id)
        assert len(segs) == 1
        assert segs[0].net_id == 7
