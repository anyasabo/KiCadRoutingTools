"""
PyGame-based real-time visualizer for PCB routing algorithm.

This visualizer shows the A* search progression in real-time as it explores
the routing grid, using the same Rust router as the batch router.

Usage:
    python route.py input.kicad_pcb output.kicad_pcb "Net-*" --visualize
"""

from .callback import NullVisualizationCallback, VisualizationCallback, VisualizationData
from .config import LayerColors, VisualizerConfig
from .pygame_callback import PyGameVisualizationCallback, create_pygame_callback
from .visualizer import RoutingVisualizer

__all__ = [
    "RoutingVisualizer",
    "VisualizerConfig",
    "LayerColors",
    "VisualizationCallback",
    "NullVisualizationCallback",
    "VisualizationData",
    "PyGameVisualizationCallback",
    "create_pygame_callback",
]
__version__ = "2.0.0"
