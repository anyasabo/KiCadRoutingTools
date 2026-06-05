#!/usr/bin/env python3
"""Add stitching vias to isolated copper zone islands.

After routing and zone fill, signal traces can divide a ground pour into
disconnected islands. This script finds those islands and adds a via at
each centroid to connect them through to the opposite-layer plane.

Usage:
    python3 stitch_zone_islands.py input.kicad_pcb output.kicad_pcb [--net GND] [--layer F.Cu]
"""

import argparse
import pcbnew
from shapely.geometry import Point, Polygon


def find_and_stitch_islands(input_path, output_path, net_name="GND", layer_name="F.Cu",
                            via_size=0.6, via_drill=0.3, min_island_area=0.5):
    board = pcbnew.LoadBoard(input_path)
    layer_id = board.GetLayerID(layer_name)

    target_zone = None
    zones = board.Zones()
    for i in range(len(zones)):
        z = zones[i]
        if z.GetNetname() == net_name and z.GetLayer() == layer_id:
            target_zone = z
            break

    if not target_zone:
        print(f"No {net_name} zone on {layer_name}")
        return

    filled = target_zone.GetFilledPolysList(layer_id)
    print(f"{layer_name} {net_name} zone: {filled.OutlineCount()} filled outlines")

    net = board.FindNet(net_name)
    net_code = net.GetNetCode()

    existing_vias = []
    for track in board.GetTracks():
        if track.GetNetCode() == net_code and track.GetClass() == "PCB_VIA":
            existing_vias.append((pcbnew.ToMM(track.GetX()), pcbnew.ToMM(track.GetY())))

    # Also include pads on this net as connection points
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net_code:
                existing_vias.append((pcbnew.ToMM(pad.GetX()), pcbnew.ToMM(pad.GetY())))

    islands = []
    for outline_idx in range(filled.OutlineCount()):
        outline = filled.Outline(outline_idx)
        pts = []
        for pt_idx in range(outline.PointCount()):
            pt = outline.CPoint(pt_idx)
            pts.append((pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)))

        if len(pts) < 3:
            continue

        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        area = poly.area

        if area < min_island_area:
            continue

        has_connection = any(poly.contains(Point(vx, vy)) for vx, vy in existing_vias)

        if not has_connection:
            centroid = poly.centroid
            islands.append((centroid.x, centroid.y, area))

    if not islands:
        print("No unconnected islands found")
        board.Save(output_path)
        return

    for x, y, area in islands:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        via.SetWidth(pcbnew.FromMM(via_size))
        via.SetDrill(pcbnew.FromMM(via_drill))
        via.SetNet(net)
        board.Add(via)
        print(f"  Added via at ({x:.2f}, {y:.2f}) for {area:.1f}mm² island")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill([zones[i] for i in range(len(zones))])
    board.Save(output_path)
    print(f"Saved {output_path} with {len(islands)} new stitching vias")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input .kicad_pcb file")
    parser.add_argument("output", help="Output .kicad_pcb file")
    parser.add_argument("--net", default="GND", help="Net name to stitch (default: GND)")
    parser.add_argument("--layer", default="F.Cu", help="Layer to check for islands (default: F.Cu)")
    parser.add_argument("--via-size", type=float, default=0.6, help="Via diameter in mm")
    parser.add_argument("--via-drill", type=float, default=0.3, help="Via drill in mm")
    parser.add_argument("--min-area", type=float, default=0.5, help="Min island area in mm²")
    args = parser.parse_args()

    find_and_stitch_islands(args.input, args.output, args.net, args.layer,
                            args.via_size, args.via_drill, args.min_area)
