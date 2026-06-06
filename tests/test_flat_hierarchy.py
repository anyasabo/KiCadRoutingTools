"""Integration test: routing on the flat_hierarchy board (2-layer, GND plane + signals)."""

from run_utils import run

GEOMETRY = "--track-width 0.5 --clearance 0.4 --via-size 0.6 --via-drill 0.5"
LAYERS = "--layers F.Cu B.Cu"
POWER = '--power-nets "GND" "VCC" "VCC_PIC" "VPP" "Net-(D1-A)" "Net-(D1-K)" --power-nets-widths 1.0 1.0 0.7 0.7 1.0 1.0'


def test_flat_hierarchy_pipeline():
    """Full pipeline: GND plane -> route signals -> DRC -> connectivity."""
    run(
        f"python3 route_planes.py kicad_files/flat_hierarchy.kicad_pcb --nets GND --plane-layers B.Cu {GEOMETRY} {POWER}"
    )
    run(f"python3 route.py kicad_files/flat_hierarchy_routed.kicad_pcb --overwrite {GEOMETRY} {LAYERS} {POWER}")
    run("python3 check_drc.py kicad_files/flat_hierarchy_routed.kicad_pcb --clearance 0.4")
    run("python3 check_connected.py kicad_files/flat_hierarchy_routed.kicad_pcb")
