"""Round-trip test: parse KiCad 10 file → write routing → reparse and verify."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kicad_parser import is_kicad_10, parse_kicad_pcb
from kicad_writer import add_tracks_and_vias_to_pcb, generate_segment_sexpr, generate_via_sexpr

MINIMAL_KICAD10_BOARD = """\
(kicad_pcb
  (version 20260206)
  (generator "pcbnew")
  (generator_version "10.0.0")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (44 "Edge.Cuts" user)
  )
  (setup
    (pad_to_mask_clearance 0)
  )
  (footprint "Package_QFP:LQFP-48_7x7mm_P0.5mm"
    (layer "F.Cu")
    (uuid "fp-001")
    (at 100 50)
    (property "Reference" "U1" (at 0 -5) (layer "F.SilkS") (uuid "ref-u1") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd roundrect
      (at -3.475 -2.5)
      (size 1.2 0.3)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (roundrect_rratio 0.25)
      (net "SIG_A")
      (uuid "pad-001")
    )
    (pad "2" smd roundrect
      (at -3.475 -2.0)
      (size 1.2 0.3)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (roundrect_rratio 0.25)
      (net "SIG_B")
      (uuid "pad-002")
    )
    (pad "13" smd roundrect
      (at 3.475 -2.5)
      (size 1.2 0.3)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (roundrect_rratio 0.25)
      (net "GND")
      (uuid "pad-013")
    )
  )
  (footprint "Resistor_SMD:R_0402_1005Metric"
    (layer "F.Cu")
    (uuid "fp-002")
    (at 110 50)
    (property "Reference" "R1" (at 0 -2) (layer "F.SilkS") (uuid "ref-r1") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd roundrect
      (at -0.48 0)
      (size 0.56 0.62)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (roundrect_rratio 0.25)
      (net "SIG_A")
      (uuid "pad-r1")
    )
    (pad "2" smd roundrect
      (at 0.48 0)
      (size 0.56 0.62)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (roundrect_rratio 0.25)
      (net "GND")
      (uuid "pad-r2")
    )
  )
  (gr_line (start 90 40) (end 120 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec1"))
  (gr_line (start 120 40) (end 120 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec2"))
  (gr_line (start 120 60) (end 90 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec3"))
  (gr_line (start 90 60) (end 90 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec4"))
)
"""


@pytest.fixture
def kicad10_board(tmp_path):
    """Write the minimal KiCad 10 board to a temp file and return the path."""
    board_path = tmp_path / "test_v10.kicad_pcb"
    board_path.write_text(MINIMAL_KICAD10_BOARD)
    return board_path


class TestKiCad10Parse:
    def test_version_detected(self, kicad10_board):
        pcb = parse_kicad_pcb(str(kicad10_board))
        assert pcb.kicad_version == 20260206

    def test_nets_discovered(self, kicad10_board):
        pcb = parse_kicad_pcb(str(kicad10_board))
        net_names = {n.name for n in pcb.nets.values()}
        assert "SIG_A" in net_names
        assert "SIG_B" in net_names
        assert "GND" in net_names

    def test_pads_assigned_correct_nets(self, kicad10_board):
        pcb = parse_kicad_pcb(str(kicad10_board))
        sig_a_id = next(nid for nid, n in pcb.nets.items() if n.name == "SIG_A")
        pads = pcb.pads_by_net[sig_a_id]
        refs = {p.component_ref for p in pads}
        assert refs == {"U1", "R1"}

    def test_footprints_parsed(self, kicad10_board):
        pcb = parse_kicad_pcb(str(kicad10_board))
        assert "fp-001" in pcb.footprints or any(fp.reference for fp in pcb.footprints.values())


class TestKiCad10RoundTrip:
    def test_write_segments_then_reparse(self, kicad10_board, tmp_path):
        """Write KiCad-10-format segments, reparse, verify net names round-trip."""
        pcb = parse_kicad_pcb(str(kicad10_board))
        sig_a_id = next(nid for nid, n in pcb.nets.items() if n.name == "SIG_A")
        gnd_id = next(nid for nid, n in pcb.nets.items() if n.name == "GND")

        tracks = [
            {"start": (96.525, 47.5), "end": (109.52, 50.0), "width": 0.2, "layer": "F.Cu", "net_id": sig_a_id},
            {"start": (103.475, 47.5), "end": (110.48, 50.0), "width": 0.2, "layer": "F.Cu", "net_id": gnd_id},
        ]
        vias = [
            {"x": 105.0, "y": 48.0, "size": 0.6, "drill": 0.3, "layers": ["F.Cu", "B.Cu"], "net_id": sig_a_id},
        ]

        output = tmp_path / "routed_v10.kicad_pcb"
        result = add_tracks_and_vias_to_pcb(
            str(kicad10_board), str(output), tracks, vias, net_id_to_name=pcb.net_id_to_name
        )
        assert result is True

        # Reparse the output
        content = output.read_text()
        assert is_kicad_10(content)

        # Verify segments use name-only format
        assert '(net "SIG_A")' in content
        assert '(net "GND")' in content

        # Verify tenting on via
        assert "(tenting (front yes) (back yes))" in content

        # Parse the output file and verify segment nets
        pcb2 = parse_kicad_pcb(str(output))
        seg_nets = {pcb2.net_id_to_name[s.net_id] for s in pcb2.segments}
        assert "SIG_A" in seg_nets
        assert "GND" in seg_nets

        # Verify via
        assert len(pcb2.vias) == 1
        assert pcb2.net_id_to_name[pcb2.vias[0].net_id] == "SIG_A"

    def test_generate_segment_sexpr_v10(self):
        """generate_segment_sexpr produces name-only net when net_name is given."""
        sexpr = generate_segment_sexpr((10.0, 20.0), (30.0, 40.0), 0.25, "F.Cu", 99, net_name="MY_NET")
        assert '(net "MY_NET")' in sexpr
        assert "(net 99)" not in sexpr

    def test_generate_segment_sexpr_v9(self):
        """generate_segment_sexpr produces numeric net when net_name is None."""
        sexpr = generate_segment_sexpr((10.0, 20.0), (30.0, 40.0), 0.25, "F.Cu", 5, net_name=None)
        assert "(net 5)" in sexpr

    def test_generate_via_sexpr_v10(self):
        """generate_via_sexpr produces tenting fields for KiCad 10."""
        sexpr = generate_via_sexpr(100.0, 50.0, 0.6, 0.3, ["F.Cu", "B.Cu"], 1, net_name="GND")
        assert '(net "GND")' in sexpr
        assert "(tenting (front yes) (back yes))" in sexpr

    def test_generate_via_sexpr_v9(self):
        """generate_via_sexpr omits tenting for KiCad 9."""
        sexpr = generate_via_sexpr(100.0, 50.0, 0.6, 0.3, ["F.Cu", "B.Cu"], 5, net_name=None)
        assert "(net 5)" in sexpr
        assert "tenting" not in sexpr
