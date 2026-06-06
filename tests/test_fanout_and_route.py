"""Integration test: full BGA fanout + routing pipeline (5-layer board)."""

from run_utils import run

GEOMETRY = "--clearance 0.1 --via-size 0.3 --via-drill 0.2 --track-width 0.1"
LAYERS_4 = "--layers F.Cu In1.Cu In2.Cu B.Cu"
LAYERS_5 = "--layers F.Cu In1.Cu In2.Cu In3.Cu B.Cu"


def test_full_pipeline(quick):
    """Full fanout + routing + planes + DRC + connectivity pipeline."""
    # --- Fanout ---
    run(
        'python3 qfn_fanout.py kicad_files/haasoscope_pro_max_test.kicad_pcb --output kicad_files/qfn_fanned_out.kicad_pcb --component U2 --nets "Net-(U2*)"'
    )
    run(
        f'python3 bga_fanout.py kicad_files/qfn_fanned_out.kicad_pcb --component U3 --output kicad_files/fanout_starting_point.kicad_pcb --nets "*U2A*DATA*" --primary-escape horizontal --force-escape-direction {LAYERS_4} --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2'
    )
    run(
        f'python3 bga_fanout.py kicad_files/fanout_starting_point.kicad_pcb --component U3 --output kicad_files/fanout_output1.kicad_pcb --nets "*U2A*" --primary-escape horizontal --check-for-previous --force-escape-direction {LAYERS_4} --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2'
    )
    run(
        f"python3 bga_fanout.py kicad_files/fanout_output1.kicad_pcb --component IC1 --output kicad_files/fanout_output2.kicad_pcb --nets '*lvds_rx*' --diff-pairs '*lvds_rx*' --primary-escape vertical {LAYERS_5} --no-inner-top-layer --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2"
    )
    run(
        f"python3 bga_fanout.py kicad_files/fanout_output2.kicad_pcb --component U3 --output kicad_files/fanout_output3.kicad_pcb --nets '*lvds_rx*' --diff-pairs '*lvds_rx*' --primary-escape vertical {LAYERS_5} --no-inner-top-layer --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2"
    )
    run(
        f'python3 bga_fanout.py kicad_files/fanout_output3.kicad_pcb --component U3 --output kicad_files/fanout_output4.kicad_pcb --nets "Net-(U1*DQS*)" "Net-(U1*CK*)" --diff-pairs "Net-(U1*DQS*)" "Net-(U1*CK*)" --primary-escape horizontal {LAYERS_4} --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2'
    )
    run(
        f'python3 bga_fanout.py kicad_files/fanout_output4.kicad_pcb --component U3 --output kicad_files/fanout_output5.kicad_pcb --nets "*U1A*" "*U1B*" --check-for-previous --primary-escape horizontal {LAYERS_4} --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2'
    )
    run(
        f'python3 bga_fanout.py kicad_files/fanout_output5.kicad_pcb --component U1 --output kicad_files/fanout_output6.kicad_pcb --nets "Net-(U1*DQS*)" "Net-(U1*CK*)" --diff-pairs "Net-(U1*DQS*)" "Net-(U1*CK*)" --primary-escape horizontal --no-inner-top-layer {LAYERS_4} --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2'
    )
    run(
        f"python3 bga_fanout.py kicad_files/fanout_output6.kicad_pcb --component U1 --output kicad_files/fanout_output7.kicad_pcb --nets '*U1A*' --check-for-previous --primary-escape horizontal {LAYERS_5} --no-inner-top-layer --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2"
    )
    run(
        f"python3 bga_fanout.py kicad_files/fanout_output7.kicad_pcb --component U1 --output kicad_files/fanout_output.kicad_pcb --nets '*U1B*' --check-for-previous {LAYERS_5} --no-inner-top-layer --track-width 0.1 --clearance 0.1 --via-size 0.3 --via-drill 0.2"
    )

    # --- FTDI routing ---
    ftdi_opts = f"--swappable-nets 'Net-(U2A-DATA_*)' --proximity-heuristic-factor 0.02 --impedance 50 --track-proximity-cost 0.2 --direction-preference-cost 0 {GEOMETRY} {LAYERS_4}"
    if quick:
        run(
            f"python3 route.py kicad_files/fanout_output.kicad_pcb kicad_files/routed_output.kicad_pcb --nets 'Net-(U2A-DATA_11*)' {ftdi_opts}"
        )
    else:
        run(
            f"python3 route.py kicad_files/fanout_output.kicad_pcb kicad_files/routed_output.kicad_pcb --nets 'Net-(U2A-*)' --mps-layer-swap {ftdi_opts}"
        )

    # --- LVDS diff pairs ---
    lvds_opts = f"--impedance 100 --proximity-heuristic-factor 0.0 {GEOMETRY} {LAYERS_5}"
    if quick:
        run(
            f"python3 route_diff.py kicad_files/routed_output.kicad_pcb kicad_files/test_diffpair.kicad_pcb --nets '*lvds_rx1_1*' --swappable-nets '*lvds_rx1_1*' {lvds_opts}"
        )
    else:
        run(
            f"python3 route_diff.py kicad_files/routed_output.kicad_pcb kicad_files/routed_output_diff12.kicad_pcb --nets '*lvds_rx1_*' '*lvds_rx2_*' '*lvds_rx*clkin1*' '*lvds_rx*clkin2*' --swappable-nets '*lvds_rx1_*' '*lvds_rx2_*' {lvds_opts}"
        )
        run(
            f"python3 route_diff.py kicad_files/routed_output_diff12.kicad_pcb kicad_files/test_diffpair.kicad_pcb --nets '*lvds_rx3_*' '*lvds_rx4_*' '*lvds_rx*clkin3*' '*lvds_rx*clkin4*' --swappable-nets '*lvds_rx3_*' '*lvds_rx4_*' {lvds_opts}"
        )

    # --- RAM routing ---
    ram_opts = (
        f"--bga-proximity-radius 1 --stub-proximity-radius 1 --proximity-heuristic-factor 0.02 {GEOMETRY} {LAYERS_5}"
    )
    run(
        f"python3 route_diff.py kicad_files/test_diffpair.kicad_pcb kicad_files/test_diffpair_ramdiff.kicad_pcb --nets 'Net-(U1*DQS*)' 'Net-(U1*CK_*)' --length-match-group 'Net-(U1*DQS*)' 'Net-(U1*CK_*)' --time-matching --mps-layer-swap --diff-pair-intra-match --heuristic-weight 1.5 {ram_opts}"
    )
    ram_se_opts = f"--swappable-nets 'Net-(U1*DQ*)' --length-match-group auto --time-matching --max-iterations 1000000 --no-bga-zones U1 {ram_opts}"
    if quick:
        run(
            f"python3 route.py kicad_files/test_diffpair_ramdiff.kicad_pcb kicad_files/test_diffpair_ram.kicad_pcb --nets 'Net-(U1B-CA*)' {ram_se_opts}"
        )
    else:
        run(
            f"python3 route.py kicad_files/test_diffpair_ramdiff.kicad_pcb kicad_files/test_diffpair_ram.kicad_pcb --nets 'Net-(U1*)' {ram_se_opts}"
        )

    # --- Planes ---
    run(
        f"python3 route_planes.py kicad_files/test_diffpair_ram.kicad_pcb kicad_files/test_diffpair_ram_planes.kicad_pcb --nets GND '/fpga_adc/VA19|/fpga_adc/VA11|/fpga_adc/VLVDS|/fpga_adc/VD11' --plane-layers In4.Cu In5.Cu --rip-blocker-nets --reroute-ripped-nets {GEOMETRY}"
    )

    # --- Checks ---
    run('python3 check_drc.py kicad_files/routed_output.kicad_pcb --clearance 0.1 --nets "Net-(U2A-*)"')
    if not quick:
        run('python3 check_connected.py kicad_files/routed_output.kicad_pcb --nets "Net-(U2A-*)"')
    run(
        'python3 check_drc.py kicad_files/test_diffpair.kicad_pcb --clearance 0.1 --nets "*lvds*" --clearance-margin 0.1'
    )
    if not quick:
        run('python3 check_connected.py kicad_files/test_diffpair.kicad_pcb --nets "*lvds*"')
    run('python3 check_drc.py kicad_files/test_diffpair_ram.kicad_pcb --clearance 0.1 --nets "Net-(U1*)"')
    if not quick:
        run('python3 check_connected.py kicad_files/test_diffpair_ram.kicad_pcb --nets "Net-(U1*)"')
    run("python3 check_drc.py kicad_files/test_diffpair_ram_planes.kicad_pcb --clearance 0.1 --clearance-margin 0.1")
    if not quick:
        run("python3 check_connected.py kicad_files/test_diffpair_ram_planes.kicad_pcb")
