"""
Controller classes for COCO widget functionality.

This module contains specialized controller classes that handle different
aspects of the COCO visualization functionality, promoting separation of
concerns and improved maintainability.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
import numpy as np
from pathlib import Path
from napari import Viewer

from ._utils import (
    load_coco_file, 
    get_category_info, 
    get_image_annotations,
    filter_annotations_by_category,
    generate_category_colors,
    CocoError
)
from ._visualization import CocoNapariVisualizer
from ._config import get_effective_config
from ._memory import get_memory_manager, memory_efficient_operation, ResourceTracker


class CocoFileManager:
    """Manages COCO file loading and data access."""
    
    def __init__(self):
        """Initialize file manager with empty state."""
        self.coco_data: Optional[Dict[str, Any]] = None
        self.file_path: Optional[Path] = None
        
    def load_file(self, file_path: str) -> Dict[str, Any]:
        """Load COCO file and store data internally."""
        self.coco_data = load_coco_file(file_path)
        self.file_path = Path(file_path)
        return self.coco_data
    
    def get_file_info(self) -> Dict[str, Any]:
        if not self.coco_data:
            return {}
        
        return {
            'num_annotations': len(self.coco_data.get('annotations', [])),
            'num_images': len(self.coco_data.get('images', [])),
            'num_categories': len(self.coco_data.get('categories', [])),
            'file_name': self.file_path.name if self.file_path else 'Unknown'
        }
    
    def is_loaded(self) -> bool:
        return self.coco_data is not None


class CategoryController:
    """Manages category filtering and color assignment."""
    
    def __init__(self):
        """Initialize category controller with empty state."""
        self.category_states: Dict[int, bool] = {}
        self.category_colors: Dict[int, tuple] = {}
        self.categories: Dict[int, Dict[str, Any]] = {}
        
    def initialize_categories(self, coco_data: Dict[str, Any]):
        """Initialize categories from COCO data and generate colors."""
        self.categories = get_category_info(coco_data)
        color_list = generate_category_colors(len(self.categories))
        
        sorted_cat_ids = sorted(self.categories.keys())
        self.category_colors = {cat_id: color_list[i] for i, cat_id in enumerate(sorted_cat_ids)}
        
        self.category_states = {cat_id: True for cat_id in self.categories.keys()}
    
    def toggle_category(self, category_id: int, enabled: bool):
        """Enable/disable specific category visibility."""
        self.category_states[category_id] = enabled
    
    def get_selected_categories(self) -> List[int]:
        """Get list of currently enabled category IDs."""
        return [cat_id for cat_id, enabled in self.category_states.items() if enabled]
    
    def select_all(self):
        """Enable all categories."""
        for cat_id in self.category_states:
            self.category_states[cat_id] = True
    
    def select_none(self):
        """Disable all categories."""
        for cat_id in self.category_states:
            self.category_states[cat_id] = False
    
    def get_category_color(self, category_id: int) -> tuple:
        """Get RGBA color tuple for specified category."""
        return self.category_colors.get(category_id, (1.0, 1.0, 1.0, 1.0))


class NavigationController:
    """Handles multi-image dataset navigation."""
    
    def __init__(self):
        """Initialize navigation controller with default state."""
        self.current_image_idx: int = 0
        self.images: List[Dict[str, Any]] = []
        
    def initialize_images(self, coco_data: Dict[str, Any]):
        """Initialize image list from COCO data."""
        self.images = coco_data.get('images', [])
        self.current_image_idx = 0
    
    def get_current_image(self) -> Optional[Dict[str, Any]]:
        """Get current image information."""
        if not self.images or self.current_image_idx >= len(self.images):
            return None
        return self.images[self.current_image_idx]
    
    def get_current_image_id(self) -> Optional[int]:
        """Get current image ID."""
        image = self.get_current_image()
        return image['id'] if image else None
    
    def navigate_to_image(self, image_idx: int) -> bool:
        """
        Navigate to specific image index.
        
        Returns
        -------
        bool
            True if navigation successful, False otherwise
        """
        if 0 <= image_idx < len(self.images):
            self.current_image_idx = image_idx
            return True
        return False
    
    def can_go_previous(self) -> bool:
        """Check if navigation to previous image is possible."""
        return self.current_image_idx > 0
    
    def can_go_next(self) -> bool:
        """Check if navigation to next image is possible."""
        return self.current_image_idx < len(self.images) - 1
    
    def go_previous(self) -> bool:
        """Navigate to previous image if possible."""
        if self.can_go_previous():
            self.current_image_idx -= 1
            return True
        return False
    
    def go_next(self) -> bool:
        """Navigate to next image if possible."""
        if self.can_go_next():
            self.current_image_idx += 1
            return True
        return False
    
    def has_multiple_images(self) -> bool:
        """Check if dataset contains multiple images."""
        return len(self.images) > 1


class VisualizationManager:
    """Manages napari layer creation and updates."""
    
    def __init__(self, viewer: Viewer):
        """Initialize visualization manager with napari viewer."""
        self.viewer = viewer
        self.current_shapes_layer = None
        self.visualizer: Optional[CocoNapariVisualizer] = None
        self.n_filter_value: Optional[int] = None
        
    def initialize_visualizer(self, coco_data: Dict[str, Any]):
        """Initialize visualization components with COCO data."""
        self.visualizer = CocoNapariVisualizer(coco_data)
    
    def set_n_filter(self, value: int):
        """Set maximum number of annotations to display."""
        self.n_filter_value = value
    
    def get_random_seed(self) -> int:
        """Get current random seed for sampling."""
        return getattr(self, '_random_seed', 42)
    
    def set_random_seed(self, seed: int):
        """Set random seed for consistent sampling."""
        self._random_seed = seed
    
    @memory_efficient_operation
    def refresh_visualization(self, 
                            image_id: int, 
                            selected_categories: List[int],
                            image_filename: str = "",
                            show_bbox: bool = True,
                            show_mask: bool = True):
        """
        Refresh visualization with current settings.
        
        Parameters
        ----------
        image_id : int
            COCO image ID to visualize
        selected_categories : list of int
            List of selected category IDs
        image_filename : str
            Image filename for layer naming
        show_bbox : bool
            Whether to display bounding boxes
        show_mask : bool  
            Whether to display masks/polygons
        """
        if not self.visualizer:
            return
        
        with ResourceTracker("refresh_visualization"):
            # Create shapes layer data with display mode options
            layer_data = self.visualizer.create_shapes_layer(
                image_id, selected_categories, show_bbox, show_mask, 
                n_filter=self.n_filter_value, random_seed=self.get_random_seed())
            
            if not layer_data:
                # Remove layer if no annotations
                self._remove_current_layer()
                return
            
            shapes_data, layer_kwargs, _ = layer_data
            
            # Note: N-filter sampling now handled at the visualization layer for consistency
            
            # Update layer name
            layer_name = f'COCO Annotations - {image_filename}' if image_filename else 'COCO Annotations'
            layer_kwargs['name'] = layer_name
            
            config = get_effective_config()
            layer_kwargs['edge_width'] = config.visualization.default_edge_width
            
            # Layer updates are faster than recreation but can fail due to napari constraints
            if self.current_shapes_layer and self.current_shapes_layer in self.viewer.layers:
                try:
                    self.current_shapes_layer.data = shapes_data
                    for key, value in layer_kwargs.items():
                        if key != 'name' and hasattr(self.current_shapes_layer, key):
                            setattr(self.current_shapes_layer, key, value)
                    self.current_shapes_layer.name = layer_name
                except Exception:
                    # Fallback when layer update constraints are violated
                    self._remove_current_layer()
                    self.current_shapes_layer = self.viewer.add_shapes(shapes_data, **layer_kwargs)
            else:
                self.current_shapes_layer = self.viewer.add_shapes(shapes_data, **layer_kwargs)
    
    def _remove_current_layer(self):
        """Remove current shapes layer from viewer."""
        if self.current_shapes_layer and self.current_shapes_layer in self.viewer.layers:
            self.viewer.layers.remove(self.current_shapes_layer)
        self.current_shapes_layer = None
    
    def cleanup(self):
        """Clean up visualization resources."""
        self._remove_current_layer()


class DisplayController:
    """Controls display options and annotation filtering."""
    
    def __init__(self):
        """Initialize display controller with default settings."""
        config = get_effective_config()
        self.n_filter_value: int = config.ui.default_n_filter
        self.random_seed: int = 42  # Fixed seed for consistent sampling
        
        self.show_bounding_boxes: bool = True
        self.show_masks: bool = True
        
    def set_n_filter(self, value: int):
        """Set N-filter value with minimum constraint."""
        self.n_filter_value = max(1, value)
    
    
    def set_annotation_display_mode(self, show_bbox: bool, show_mask: bool):
        """Configure which annotation types to display."""
        self.show_bounding_boxes = show_bbox
        self.show_masks = show_mask
    
    def resample(self):
        """Generate new random seed for resampling annotations."""
        import random
        self.random_seed = random.randint(1, 10000)
        print(f"New random seed: {self.random_seed}")
    
    def determine_default_display_modes(self, coco_data: Dict[str, Any]) -> Tuple[bool, bool]:
        """
        Determine default display modes based on available annotation types.
        
        Returns mask preference if segmentation data exists, otherwise bbox.
        
        Parameters
        ----------
        coco_data : dict
            COCO data to analyze
            
        Returns
        -------
        tuple of bool
            (show_bbox, show_mask) - defaults based on available data
        """
        if not coco_data or not coco_data.get('annotations'):
            return True, True  # Default to both if no data
        
        annotations = coco_data.get('annotations', [])
        has_segmentation = any('segmentation' in ann for ann in annotations)
        has_bbox = any('bbox' in ann for ann in annotations)
        
        if has_segmentation:
            # Show both by default when segmentation available for maximum info
            return True, True
        elif has_bbox:
            return True, False
        else:
            return True, True
    
    def get_annotation_count_info(self, 
                                coco_data: Dict[str, Any], 
                                image_id: int,
                                selected_categories: List[int]) -> Dict[str, int]:
        """
        Get annotation count information for current settings.
        
        Returns
        -------
        dict
            Dictionary with 'visible' and 'total' annotation counts
        """
        if not coco_data:
            return {'visible': 0, 'total': 0}
        
        total_annotations = len(coco_data.get('annotations', []))
        
        image_annotations = get_image_annotations(coco_data, image_id)
        
        if selected_categories:
            image_annotations = filter_annotations_by_category(image_annotations, selected_categories)
        
        visible_count = len(image_annotations)
        
        return {'visible': visible_count, 'total': total_annotations}