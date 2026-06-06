"""Integration test: routing on kit-dev-coldfire-xilinx_5213 board (4-layer, pad-to-pad)."""

from run_utils import run

BASE_OPTIONS = "--track-width 0.2 --clearance 0.2 --via-size 0.5 --via-drill 0.4 --hole-to-hole-clearance 0.3 --layers F.Cu In1.Cu In2.Cu B.Cu"
POWER_NETS = '--power-nets "GND" "+3.3V" "GNDA" "/VDDPLL" "/VCCA" "Net-(TB201-P1)" "Net-(F201-Pad1)" "Net-(D201-K)" --power-nets-widths 0.5 0.5 0.3 0.3 0.3 0.5 0.5 0.5'
ROUTE_OPTIONS = (
    f"{BASE_OPTIONS} --proximity-heuristic-factor 0.02 --direction-preference-cost 50 "
    f"--ripped-route-avoidance-radius 1.0 --ripped-route-avoidance-cost 10.0 "
    f"--via-proximity-cost 10 --via-cost 300 --track-proximity-distance 3.0 --track-proximity-cost 0.0 "
    f"--vertical-attraction-cost 0.0 --stub-proximity-cost 4.0 --stub-proximity-radius 5.0 "
    f"--max-ripup 10 --max-iterations 10000000 --bus --bus-detection-radius 5 "
    f"--bus-attraction-bonus 5000 --bus-attraction-radius 1 {POWER_NETS}"
)


def test_kit_route_pipeline():
    """Full pipeline: route -> planes -> disconnect repair -> DRC -> connectivity -> orphan stubs."""
    target = '--nets "/*" "Net-*" GNDA'
    run(
        f"python3 route.py kicad_files/kit-dev-coldfire-xilinx_5213.kicad_pcb kicad_files/kit-out.kicad_pcb {target} {ROUTE_OPTIONS}"
    )
    run(
        f"python3 route_planes.py kicad_files/kit-out.kicad_pcb kicad_files/kit-out-plane.kicad_pcb --nets +3.3V GND +3.3V GND --plane-layers F.Cu In1.Cu In2.Cu B.Cu --max-via-reuse-radius 3 --rip-blocker-nets --reroute-ripped-nets {BASE_OPTIONS}"
    )
    run(
        f"python3 route_disconnected_planes.py kicad_files/kit-out-plane.kicad_pcb kicad_files/kit-out-plane-connected.kicad_pcb --analysis-grid-step 0.1 {BASE_OPTIONS}"
    )
    run(
        "python3 check_drc.py kicad_files/kit-out-plane-connected.kicad_pcb --clearance 0.2 --hole-to-hole-clearance 0.3"
    )
    run(f"python3 check_connected.py kicad_files/kit-out-plane-connected.kicad_pcb {target}")
    run("python3 check_orphan_stubs.py kicad_files/kit-out-plane-connected.kicad_pcb")
