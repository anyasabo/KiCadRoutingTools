"""Regression test: custom pad primitives (gr_poly) bounding box and center calculation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kicad_parser import parse_kicad_pcb

BOARD_WITH_CUSTOM_PAD = """\
(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
  )
  (net 0 "")
  (net 1 "NET1")
  (footprint "Custom:MyPad"
    (layer "F.Cu")
    (uuid "fp-custom")
    (at 100 50 0)
    (property "Reference" "U1" (at 0 0) (layer "F.SilkS") (uuid "ref1") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd custom
      (at 0 0)
      (size 0.5 0.5)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (net 1 "NET1")
      (uuid "pad-c1")
      (primitives
        (gr_poly
          (pts
            (xy -2.0 -1.0)
            (xy 2.0 -1.0)
            (xy 2.0 1.0)
            (xy -2.0 1.0)
          )
          (width 0)
          (fill yes)
        )
      )
    )
  )
  (gr_line (start 90 40) (end 110 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec1"))
  (gr_line (start 110 40) (end 110 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec2"))
  (gr_line (start 110 60) (end 90 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec3"))
  (gr_line (start 90 60) (end 90 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec4"))
)
"""

BOARD_WITH_OFFSET_CUSTOM_PAD = """\
(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
  )
  (net 0 "")
  (net 1 "NET1")
  (footprint "Custom:OffsetPad"
    (layer "F.Cu")
    (uuid "fp-offset")
    (at 100 50 0)
    (property "Reference" "U2" (at 0 0) (layer "F.SilkS") (uuid "ref2") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd custom
      (at 5 3)
      (size 0.5 0.5)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (net 1 "NET1")
      (uuid "pad-off1")
      (primitives
        (gr_poly
          (pts
            (xy -1.5 -2.0)
            (xy 1.5 -2.0)
            (xy 1.5 2.0)
            (xy -1.5 2.0)
          )
          (width 0)
          (fill yes)
        )
      )
    )
  )
  (gr_line (start 90 40) (end 120 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec1"))
  (gr_line (start 120 40) (end 120 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec2"))
  (gr_line (start 120 60) (end 90 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec3"))
  (gr_line (start 90 60) (end 90 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec4"))
)
"""

BOARD_WITH_ROTATED_FOOTPRINT = """\
(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
  )
  (net 0 "")
  (net 1 "NET1")
  (footprint "Custom:RotatedPad"
    (layer "F.Cu")
    (uuid "fp-rot")
    (at 100 50 90)
    (property "Reference" "U3" (at 0 0) (layer "F.SilkS") (uuid "ref3") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd custom
      (at 0 0)
      (size 0.5 0.5)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (net 1 "NET1")
      (uuid "pad-rot1")
      (primitives
        (gr_poly
          (pts
            (xy -3.0 -1.0)
            (xy 3.0 -1.0)
            (xy 3.0 1.0)
            (xy -3.0 1.0)
          )
          (width 0)
          (fill yes)
        )
      )
    )
  )
  (gr_line (start 90 40) (end 110 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec1"))
  (gr_line (start 110 40) (end 110 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec2"))
  (gr_line (start 110 60) (end 90 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec3"))
  (gr_line (start 90 60) (end 90 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec4"))
)
"""


@pytest.fixture
def custom_pad_board(tmp_path):
    p = tmp_path / "custom_pad.kicad_pcb"
    p.write_text(BOARD_WITH_CUSTOM_PAD)
    return p


@pytest.fixture
def offset_pad_board(tmp_path):
    p = tmp_path / "offset_pad.kicad_pcb"
    p.write_text(BOARD_WITH_OFFSET_CUSTOM_PAD)
    return p


@pytest.fixture
def rotated_fp_board(tmp_path):
    p = tmp_path / "rotated_fp.kicad_pcb"
    p.write_text(BOARD_WITH_ROTATED_FOOTPRINT)
    return p


class TestCustomPadPrimitives:
    def test_bounding_box_from_primitives(self, custom_pad_board):
        """Custom pad size should come from gr_poly bounding box, not anchor size."""
        pcb = parse_kicad_pcb(str(custom_pad_board))
        pad = pcb.pads_by_net[1][0]
        assert abs(pad.size_x - 4.0) < 1e-6
        assert abs(pad.size_y - 2.0) < 1e-6

    def test_center_at_footprint_origin(self, custom_pad_board):
        """Symmetric custom pad centered at footprint origin → global pos = footprint pos."""
        pcb = parse_kicad_pcb(str(custom_pad_board))
        pad = pcb.pads_by_net[1][0]
        assert abs(pad.global_x - 100.0) < 1e-6
        assert abs(pad.global_y - 50.0) < 1e-6

    def test_offset_pad_center(self, offset_pad_board):
        """Custom pad with local offset (5, 3) + symmetric primitives → center at (105, 53)."""
        pcb = parse_kicad_pcb(str(offset_pad_board))
        pad = pcb.pads_by_net[1][0]
        assert abs(pad.global_x - 105.0) < 1e-6
        assert abs(pad.global_y - 53.0) < 1e-6
        assert abs(pad.size_x - 3.0) < 1e-6
        assert abs(pad.size_y - 4.0) < 1e-6

    def test_rotated_footprint_custom_pad(self, rotated_fp_board):
        """Custom pad in 90-degree-rotated footprint → global position rotated."""
        pcb = parse_kicad_pcb(str(rotated_fp_board))
        pad = pcb.pads_by_net[1][0]
        # Primitives are 6x2 in local coords; footprint at 90° rotates the center
        # but primitives centroid is (0,0) so global stays at footprint center
        assert abs(pad.global_x - 100.0) < 1e-6
        assert abs(pad.global_y - 50.0) < 1e-6
        # size_x/size_y are computed from primitives BEFORE rotation
        assert abs(pad.size_x - 6.0) < 1e-6
        assert abs(pad.size_y - 2.0) < 1e-6

    def test_non_custom_pad_ignores_anchor_override(self, tmp_path):
        """Regular pad shape uses declared size, not primitives."""
        content = """\
(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
  )
  (net 0 "")
  (net 1 "NET1")
  (footprint "SMD:R0402"
    (layer "F.Cu")
    (uuid "fp-r")
    (at 100 50 0)
    (property "Reference" "R1" (at 0 0) (layer "F.SilkS") (uuid "ref-r") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd rect
      (at 0 0)
      (size 1.2 0.6)
      (layers "F.Cu" "F.Paste" "F.Mask")
      (net 1 "NET1")
      (uuid "pad-rect")
    )
  )
  (gr_line (start 90 40) (end 110 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec1"))
  (gr_line (start 110 40) (end 110 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec2"))
  (gr_line (start 110 60) (end 90 60) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec3"))
  (gr_line (start 90 60) (end 90 40) (stroke (width 0.05) (type solid)) (layer "Edge.Cuts") (uuid "ec4"))
)
"""
        p = tmp_path / "rect_pad.kicad_pcb"
        p.write_text(content)
        pcb = parse_kicad_pcb(str(p))
        pad = pcb.pads_by_net[1][0]
        assert abs(pad.size_x - 1.2) < 1e-6
        assert abs(pad.size_y - 0.6) < 1e-6
