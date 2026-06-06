"""Integration test: routing on the interf_u board (2-layer, non-rectangular, PGA120)."""

from run_utils import run


def test_interf_u_pipeline():
    """Full pipeline: planes -> fanout -> route -> connect planes -> DRC -> connectivity."""
    run(
        "python3 route_planes.py kicad_files/interf_u_unrouted.kicad_pcb kicad_files/interf_u_plane.kicad_pcb --nets VCC GND --plane-layers F.Cu B.Cu"
    )
    run(
        'python3 bga_fanout.py kicad_files/interf_u_plane.kicad_pcb --component U9 --output kicad_files/interf_u_fanout.kicad_pcb --nets "/*"'
    )
    run(
        "python3 route.py kicad_files/interf_u_fanout.kicad_pcb kicad_files/interf_u_routed.kicad_pcb --no-bga-zone --add-teardrops --layer-costs 1 1 --max-ripup 10 --stub-proximity-radius 10 --stub-proximity-cost 3.0 --max-iterations 1000000 --board-edge-clearance 0.55"
    )
    run(
        "python3 route_disconnected_planes.py kicad_files/interf_u_routed.kicad_pcb kicad_files/interf_u_connected.kicad_pcb --board-edge-clearance 0.6"
    )
    run("python3 check_drc.py kicad_files/interf_u_connected.kicad_pcb")
    run("python3 check_connected.py kicad_files/interf_u_connected.kicad_pcb")
