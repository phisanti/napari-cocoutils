"""
napari-cocoutils plugin for visualizing COCO annotation datasets.

This plugin provides functionality to load and visualize COCO JSON annotation files
in napari, with interactive controls for category management and multi-image navigation.
Built on the proven cocoutils library.
"""

__version__ = "0.1.0"

# Import main functions for easy access
from ._reader import coco_reader
from ._widget import CocoWidget
from ._utils import load_coco_file, validate_coco_structure, CocoError

__all__ = [
    'coco_reader',
    'CocoWidget', 
    'load_coco_file',
    'validate_coco_structure',
    'CocoError',
]