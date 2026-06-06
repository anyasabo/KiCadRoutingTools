"""
Data types for BGA fanout routing.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kicad_parser import Pad


@dataclass
class Channel:
    """A routing channel between ball rows/columns."""

    orientation: str  # 'horizontal' or 'vertical'
    position: float  # Y for horizontal, X for vertical
    index: int


@dataclass
class BGAGrid:
    """Represents the BGA ball grid structure."""

    pitch_x: float
    pitch_y: float
    rows: list[float]  # Sorted Y positions
    cols: list[float]  # Sorted X positions
    center_x: float
    center_y: float
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass
class DiffPairPads:
    """A differential pair of pads (P and N) - tracks pad objects."""

    base_name: str  # Common name without _P/_N suffix
    p_pad: "Pad | None" = None
    n_pad: "Pad | None" = None

    @property
    def is_complete(self) -> bool:
        return self.p_pad is not None and self.n_pad is not None


@dataclass
class FanoutRoute:
    """Complete fanout: pad -> 45° stub -> channel -> exit -> jog."""

    pad: "Pad"
    pad_pos: tuple[float, float]
    stub_end: tuple[float, float]  # Where stub meets channel (or exit for edge pads)
    exit_pos: tuple[float, float]  # Where route exits BGA
    jog_end: tuple[float, float] | None = None
    jog_extension: tuple[float, float] | None = None
    channel_point: tuple[float, float] | None = None
    channel_point2: tuple[float, float] | None = None
    pre_channel_jog: tuple[float, float] | None = None
    channel: Channel | None = None  # None for edge pads with direct escape
    escape_dir: str = ""  # 'left', 'right', 'up', 'down'
    is_edge: bool = False  # True for outer row/column pads
    layer: str = "F.Cu"
    pair_id: str | None = None  # Differential pair base name if part of a pair
    is_p: bool = True  # True for P, False for N in differential pair
    neighbor_connection: bool = False  # True if this connects directly to adjacent same-net pad

    @property
    def net_id(self) -> int:
        return self.pad.net_id


def create_track(
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    layer: str,
    net_id: int,
    pair_id: str | None = None,
    is_existing: bool = False,
) -> dict:
    """
    Factory function to create a track dictionary.

    This provides a single point for track creation, making it easier to
    ensure consistency and eventually migrate to the Track dataclass.
    """
    d = {
        "start": start,
        "end": end,
        "width": width,
        "layer": layer,
        "net_id": net_id,
    }
    if pair_id is not None:
        d["pair_id"] = pair_id
    if is_existing:
        d["is_existing"] = is_existing
    return d
