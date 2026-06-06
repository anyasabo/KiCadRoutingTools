"""Integration test: routing on the sonde_u board (wide tracks)."""

from run_utils import run


def test_sonde_u_pipeline():
    """Full pipeline: route -> GND plane -> DRC -> connectivity."""
    run("python3 route.py kicad_files/sonde_u.kicad_pcb")
    run("python3 route_planes.py kicad_files/sonde_u_routed.kicad_pcb --nets GND --plane-layers B.Cu --add-gnd-vias")
    run("python3 check_drc.py kicad_files/sonde_u_routed.kicad_pcb --clearance 0.2")
    run("python3 check_connected.py kicad_files/sonde_u_routed.kicad_pcb")
