"""
Utility functions and bridge to cocoutils library.

This module provides helper functions and serves as the main interface
to the cocoutils library, handling data conversion, validation, and
shared functionality between different plugin components.
"""

from typing import Dict, List, Any, Optional, Union, Tuple, Protocol
import json
import numpy as np
from pathlib import Path
import sys
import os
import logging

from cocoutils.utils.categories import CategoryManager
from cocoutils.utils.io import load_coco as cocoutils_load
from cocoutils.visualise import CocoVisualizer

logger = logging.getLogger(__name__)


class CocoAnnotation(Protocol):
    id: int
    image_id: int
    category_id: int
    area: Optional[float]
    bbox: Optional[List[float]]
    segmentation: Optional[List[List[float]]]


class CocoCategory(Protocol):
    id: int
    name: str
    supercategory: Optional[str]


class CocoImage(Protocol):
    id: int
    file_name: str
    width: int
    height: int


class CocoDataset(Protocol):
    images: List[CocoImage]
    categories: List[CocoCategory]
    annotations: List[CocoAnnotation]


class CocoError(Exception):
    def __init__(self, message: str, user_message: Optional[str] = None):
        self.message = message
        self.user_message = user_message or message
        super().__init__(message)


def load_coco_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load and validate a COCO JSON file.
    
    Parameters
    ----------
    file_path : str or Path
        Path to the COCO JSON file
        
    Returns
    -------
    dict
        Loaded COCO data dictionary
        
    Raises
    ------
    CocoError
        If file cannot be loaded or is invalid format
    """
    try:
        data = cocoutils_load(str(file_path))
        if data is None:
            raise CocoError(
                f"Failed to load COCO file: {file_path}",
                "File could not be loaded. Please check the file format."
            )
        return data
    except FileNotFoundError:
        raise CocoError(
            f"COCO file not found: {file_path}",
            "Selected file could not be found. Please check the file path."
        )
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        raise CocoError(
            f"Invalid JSON in COCO file: {e}",
            "File is not valid JSON format. Please select a valid COCO file."
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Unexpected error loading COCO file {file_path}: {e}")
        logger.error(f"Full traceback: {error_details}")
        
        # Provide more specific error messages based on common issues
        error_str = str(e).lower()
        if "module" in error_str and "not found" in error_str:
            raise CocoError(
                f"Missing dependency: {e}",
                "Required dependency not found. Please check cocoutils installation."
            )
        elif "attribute" in error_str:
            raise CocoError(
                f"cocoutils API error: {e}",
                "Incompatible cocoutils version. Please check installation."
            )
        else:
            raise CocoError(
                f"Error loading COCO file: {e}",
                f"Unexpected error: {str(e)[:100]}..."
            )


def validate_coco_structure(data: Optional[Dict[str, Any]]) -> bool:
    """
    Validate that dictionary contains valid COCO structure.
    
    Parameters
    ----------
    data : dict
        Dictionary to validate as COCO format
        
    Returns
    -------
    bool
        True if valid COCO structure, False otherwise
    """
    if data is None:
        return False
        
    required_fields = ['images', 'annotations', 'categories']
    for field in required_fields:
        if field not in data:
            return False
        if not isinstance(data[field], list):
            return False
    
    try:
        for img in data['images']:
            if not all(key in img for key in ['id', 'file_name', 'width', 'height']):
                return False
        
        for ann in data['annotations']:
            if not all(key in ann for key in ['id', 'image_id', 'category_id']):
                return False
        
        for cat in data['categories']:
            if not all(key in cat for key in ['id', 'name']):
                return False
                
        return True
    except (KeyError, TypeError):
        return False


def get_image_annotations(coco_data: Dict[str, Any], image_id: int) -> List[Dict[str, Any]]:
    """
    Get all annotations for a specific image.
    
    Parameters
    ----------
    coco_data : dict
        COCO data structure
    image_id : int
        ID of the image to get annotations for
        
    Returns
    -------
    list of dict
        List of annotation dictionaries for the specified image
    """
    annotations = [ann for ann in coco_data.get('annotations', []) 
                   if ann.get('image_id') == image_id]
    return sorted(annotations, key=lambda x: x.get('id', 0))


def filter_annotations_by_category(annotations: List[Dict[str, Any]], 
                                 category_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Filter annotations by category IDs.
    
    Parameters
    ----------
    annotations : list of dict
        List of COCO annotation dictionaries
    category_ids : list of int
        List of category IDs to include
        
    Returns
    -------
    list of dict
        Filtered list of annotations
    """
    if not category_ids:
        return []
    
    return [ann for ann in annotations 
            if ann.get('category_id') in category_ids]


def get_category_info(coco_data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """
    Extract category information as lookup dictionary.
    
    Parameters
    ----------
    coco_data : dict
        COCO data structure
        
    Returns
    -------
    dict
        Mapping from category ID to category information
    """
    return {cat['id']: cat for cat in coco_data.get('categories', [])}


def generate_category_colors(num_categories: int) -> List[Tuple[float, float, float, float]]:
    """
    Generate distinct colors for categories.
    
    Parameters
    ----------
    num_categories : int
        Number of distinct colors needed
        
    Returns
    -------
    list of tuple
        List of RGBA color tuples (values 0-1) for napari compatibility
    """
    import matplotlib.pyplot as plt
    
    if num_categories == 0:
        return []
    
    cmap_name = 'tab20' if num_categories <= 20 else 'hsv'
    cmap = plt.colormaps.get_cmap(cmap_name)
    
    if num_categories <= 20:
        indices = np.arange(num_categories)
    else:
        indices = np.linspace(0, 1, num_categories, endpoint=False)
    
    colors = cmap(indices)
    
    return [tuple(color) for color in colors]


def convert_napari_to_coco_coordinates(points: np.ndarray) -> List[float]:
    """
    Convert napari shape coordinates to COCO format.
    
    Parameters
    ----------
    points : numpy.ndarray
        Napari shape points in (N, 2) format [row, col]
        
    Returns
    -------
    list of float
        COCO polygon format [x1, y1, x2, y2, ...]
    """
    coco_points = []
    for row, col in points:
        coco_points.extend([float(col), float(row)])
    return coco_points


def convert_coco_to_napari_coordinates(polygon: List[float]) -> np.ndarray:
    """
    Convert COCO polygon coordinates to napari format.
    
    Parameters
    ----------
    polygon : list of float
        COCO polygon in [x1, y1, x2, y2, ...] format
        
    Returns
    -------
    numpy.ndarray
        Napari shape points in (N, 2) format [row, col]
    """
    points = np.array(polygon).reshape(-1, 2)
    napari_points = np.column_stack([points[:, 1], points[:, 0]])
    return napari_points


def setup_cocoutils_integration() -> bool:
    """
    Initialize integration with cocoutils library.
    
    Returns
    -------
    bool
        True if cocoutils is available and working, False otherwise
    """
    try:
        # Test cocoutils imports
        from cocoutils.utils.categories import CategoryManager
        from cocoutils.utils.io import load_coco as cocoutils_load
        
        # Test basic functionality - just test imports for now  
        # CategoryManager may require different initialization
        print("✓ cocoutils integration successful")
        return True
    except ImportError as e:
        logger.error(f"cocoutils import error: {e}")
        print(f"✗ cocoutils import error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error initializing cocoutils: {e}")
        print(f"✗ cocoutils initialization error: {e}")
        return False


def get_cocoutils_visualizer(coco_data: Dict[str, Any]) -> Optional[CocoVisualizer]:
    """
    Get cocoutils visualizer instance for color schemes.
    
    Parameters
    ----------
    coco_data : dict
        COCO data structure
        
    Returns
    -------
    CocoVisualizer or None
        Cocoutils visualizer instance, or None if not available
    """
    try:
        return CocoVisualizer(coco_data)
    except Exception as e:
        logger.error(f"Error creating cocoutils visualizer: {e}")
        return None


def diagnose_coco_file(file_path: str) -> str:
    """
    Diagnose issues with a COCO file for debugging.
    
    Parameters
    ----------
    file_path : str
        Path to COCO file to diagnose
        
    Returns
    -------
    str
        Diagnostic information
    """
    diagnostics = []
    
    try:
        # Check file existence and permissions
        from pathlib import Path
        path_obj = Path(file_path)
        if not path_obj.exists():
            return f"File does not exist: {file_path}"
        if not path_obj.is_file():
            return f"Path is not a file: {file_path}"
        if not path_obj.suffix.lower() == '.json':
            diagnostics.append("Warning: File does not have .json extension")
        
        # Check file size
        file_size = path_obj.stat().st_size
        diagnostics.append(f"File size: {file_size} bytes")
        
        # Try to load as JSON
        import json
        with open(file_path, 'r') as f:
            data = json.load(f)
        diagnostics.append("✓ Valid JSON format")
        
        # Check COCO structure
        if validate_coco_structure(data):
            diagnostics.append("✓ Valid COCO structure")
        else:
            diagnostics.append("✗ Invalid COCO structure")
        
        # Check data contents
        if data:
            diagnostics.append(f"Images: {len(data.get('images', []))}")
            diagnostics.append(f"Categories: {len(data.get('categories', []))}")
            diagnostics.append(f"Annotations: {len(data.get('annotations', []))}")
        
        # Test cocoutils integration
        if setup_cocoutils_integration():
            try:
                cocoutils_data = cocoutils_load(str(file_path))
                if cocoutils_data:
                    diagnostics.append("✓ cocoutils can load file")
                else:
                    diagnostics.append("✗ cocoutils returned None")
            except Exception as e:
                diagnostics.append(f"✗ cocoutils error: {str(e)}")
        else:
            diagnostics.append("✗ cocoutils integration failed")
            
    except Exception as e:
        diagnostics.append(f"✗ Error during diagnosis: {str(e)}")
    
    return "\n".join(diagnostics)