# Gap Analysis: KiCadRoutingTools vs Freerouting

Comparative analysis focused on KiCad 10+ workflows. Freerouting is a mature
Java-based autorouter using maze search (Lee algorithm) with DSN/SES file
exchange. KRT is a Rust-accelerated A* router operating directly on `.kicad_pcb`
files.

## Where KRT Already Leads

| Capability | KRT | Freerouting |
|---|---|---|
| Native .kicad_pcb read/write | Yes (KiCad 9 + 10) | No — requires DSN/SES round-trip |
| KiCad 10 net format | Supported | Indirect via DSN export |
| Differential pair routing | First-class (pose-based A*, Dubins heuristic) | Not implemented |
| Length matching / meanders | Built-in, DDR byte-lane aware | Not implemented |
| Impedance-controlled routing | IPC-2141 microstrip/stripline auto-width | Not implemented |
| Routing speed | Seconds (Rust A* core) | Minutes (Java maze search) |
| BGA/QFN fanout | Integrated with escape routing | Basic SMD fanout pre-pass |
| Power plane via-stitching | Voronoi partitioning + MST | Not a distinct feature |
| Target/pad swap optimization | Hungarian algorithm + schematic sync | Not implemented |
| Guide corridors | User-layer polylines | Not available |

## Improvements to Make

Ordered by priority. Check off as completed.

### 1. Blind/Buried Via Support [High]

KRT only places through-hole vias. Modern HDI boards (4+ layers) require vias
spanning a subset of layers. KiCad 10 `.kicad_pcb` already stores via layer
ranges in `(via ... (layers F.Cu In1.Cu))` syntax.

Work needed:
- Parse via definitions with layer ranges from the PCB file
- Extend the A* state space to allow layer-restricted transitions
- Respect padstack definitions when building the obstacle map
- Add CLI flags: `--via-type through|blind|buried|micro`
- Update DRC checking to validate layer span legality

### 2. Per-Net-Class Design Rules [High]

KRT uses global clearances and track widths. Real KiCad projects define net
classes with distinct clearance, track width, and via size. The `(net_class ...)`
section in `.kicad_pcb` contains all of this.

Work needed:
- Parse net class definitions and net-to-class assignments
- Build per-net obstacle clearances (different nets may have different keepaway)
- Apply per-net track widths during routing (extends existing per-layer width)
- Apply per-net via sizes
- Handle the "Default" net class as fallback

### 3. Post-Route Pull-Tight Optimization [Medium]

After all nets are routed, run a pass that shortens traces by removing
unnecessary bends and straightening segments. Freerouting's pull-tight reduces
total trace length 5-15% without violating DRC.

Work needed:
- For each routed trace, try removing each intermediate waypoint
- Check if the simplified path (skip the point, connect neighbors directly) is DRC-clean
- Greedily accept shortenings that pass clearance
- Optionally iterate until no further improvement
- Preserve length-matched groups (don't shorten those)

### 4. Automatic Neckdown [Medium]

When a trace approaches a pad or via whose annular ring is smaller than the
trace width, automatically reduce width for the final segment to avoid DRC
violations. Critical for BGA escape routing with tight pad pitch.

Work needed:
- Detect when trace width exceeds pad/via entry clearance
- Taper the last grid step(s) to a narrower width
- Configurable: `--neckdown auto|off`
- Respect minimum trace width from design rules

### 5. Multi-Threaded Net Routing [Medium, Long-term]

KRT routes nets sequentially. For large boards (500+ nets), independent nets
that don't share obstacle space could route in parallel.

Work needed:
- Identify independent net clusters (no shared bounding-box overlap)
- Route clusters in parallel threads
- Merge obstacle maps after each cluster completes
- Fall back to sequential for nets in congested regions
- Rust's rayon crate is a natural fit

### 6. Any-Angle Routing Option [Low]

KRT is octilinear (8 directions). Any-angle routing is niche but useful for
RF/analog where trace impedance depends on geometry. Low priority since 45-degree
is the industry standard.

Work needed:
- Add a continuous-angle mode to the A* expansion
- Snap final traces to manufacturing grid
- Likely a separate router mode, not a modification of the main loop

## Not Worth Porting from Freerouting

- **DSN/SES format support** — native .kicad_pcb is strictly better; DSN
  round-trips lose keepouts, custom zones, and user-layer data.
- **Java Swing GUI** — KRT's KiCad plugin GUI is integrated where users work.
- **Maze search algorithm** — A* with Rust is faster and comparable quality.
- **REST API / MCP server** — KRT's CLI + Claude Code skills are a better fit.
- **Stagnation detection with adaptive costs** — KRT's N+1 rip-up strategy
  works; adaptive costs add complexity for marginal gain.

## Reference

- Freerouting source: https://github.com/freerouting/freerouting
- KRT Rust router: `src/lib.rs` (GridRouter, PoseRouter, DubinsCalculator)
- KRT obstacle map: `obstacle_map.py`, `obstacle_cache.py`
- KRT config: `routing_config.py`, `routing_defaults.py`
