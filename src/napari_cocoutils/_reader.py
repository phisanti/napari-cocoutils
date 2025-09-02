"""
COCO file reader for napari.

This module implements the napari reader hook that detects and loads COCO JSON files,
converting them into appropriate napari layers (image + shapes) for visualization.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import json
import numpy as np
from pathlib import Path
from napari.types import LayerDataTuple

from ._utils import (
    load_coco_file, 
    validate_coco_structure, 
    get_image_annotations,
    get_category_info,
    convert_coco_to_napari_coordinates,
    generate_category_colors
)
from ._progress import progress_context


def coco_reader(path: Union[str, List[str]]) -> Optional[List[LayerDataTuple]]:
    """
    Read COCO JSON annotation file and return napari-compatible layer data.
    
    This function serves as the main napari reader hook for COCO files.
    It validates the JSON structure, loads image and annotation data using
    cocoutils, and converts the data into napari layer format.
    
    Parameters
    ----------
    path : str or list of str
        Path to the COCO JSON file(s) to read
        
    Returns
    -------
    list of LayerDataTuple or None
        List of (data, meta, layer_type) tuples for napari layers,
        or None if file cannot be read as COCO format
    """
    if isinstance(path, list):
        if len(path) == 1:
            path = path[0]
        else:
            # Multiple files not supported - napari typically loads single annotation files
            return None
    
    if not _is_coco_file(path):
        return None
    
    try:
        with progress_context("Loading COCO file...", "console") as reporter:
            reporter.update(0, 2, "Loading COCO data")
            coco_data = load_coco_file(path)
            
            if coco_data is None:
                return None
            
            reporter.update(1, 2, "Converting to napari format")
            result = _convert_coco_to_napari(coco_data, path, reporter)
            
            reporter.update(2, 2, "Completed")
            return result
            
    except Exception as e:
        print(f"Error loading COCO file: {e}")
        return None


def _is_coco_file(path: str) -> bool:
    """
    Check if a JSON file contains valid COCO format data.
    
    Parameters
    ----------
    path : str
        Path to JSON file to validate
        
    Returns
    -------
    bool
        True if file contains valid COCO structure, False otherwise
    """
    try:
        if not str(path).endswith('.json'):
            return False
        with open(path, 'r') as f:
            data = json.load(f)
        
        return validate_coco_structure(data)
        
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return False


def _convert_coco_to_napari(coco_data: Dict[str, Any], coco_path: str, reporter=None) -> List[LayerDataTuple]:
    """
    Convert COCO data structure to napari layer format.
    
    Parameters
    ----------
    coco_data : dict
        Loaded COCO JSON data structure
    coco_path : str
        Path to COCO file (for resolving image paths)
        
    Returns
    -------
    list of LayerDataTuple
        Napari-compatible layer data tuples
    """
    layers = []
    
    categories = get_category_info(coco_data)
    if categories:
        category_colors = generate_category_colors(len(categories))
        color_map = {cat_id: color for cat_id, color in zip(categories.keys(), category_colors)}
    else:
        color_map = {}
    
    # Create shapes layer - image layers handled separately via file manager
    all_shapes = []
    all_properties = []
    all_shape_types = []
    all_colors = []
    
    annotations = coco_data.get('annotations', [])
    total_annotations = len(annotations)
    
    for i, annotation in enumerate(annotations):
        if reporter and i % 100 == 0:  # Update progress every 100 annotations
            reporter.update(i, total_annotations, f"Processing annotation {i+1}/{total_annotations}")
        if 'segmentation' in annotation and annotation['segmentation']:
            for seg in annotation['segmentation']:
                if len(seg) >= 6:  # At least 3 points (6 coordinates)
                    try:
                        napari_points = convert_coco_to_napari_coordinates(seg)
                        all_shapes.append(napari_points)
                        all_shape_types.append('polygon')
                        
                        category_id = annotation.get('category_id', 1)
                        category_name = categories.get(category_id, {}).get('name', f'category_{category_id}')
                        all_properties.append({
                            'category_id': category_id,
                            'category_name': category_name,
                            'annotation_id': annotation.get('id', 0),
                            'area': annotation.get('area', 0)
                        })
                        
                        color = color_map.get(category_id, (1.0, 1.0, 1.0, 1.0))
                        all_colors.append(color)
                    except Exception as e:
                        print(f"Error processing segmentation: {e}")
                        continue
        
        # Handle bounding box as fallback when no segmentation available
        elif 'bbox' in annotation:
            try:
                x, y, w, h = annotation['bbox']
                rect_points = np.array([
                    [y, x],           # top-left
                    [y, x + w],       # top-right
                    [y + h, x + w],   # bottom-right
                    [y + h, x]        # bottom-left
                ])
                all_shapes.append(rect_points)
                all_shape_types.append('polygon')
                
                # Add properties
                category_id = annotation.get('category_id', 1)
                category_name = categories.get(category_id, {}).get('name', f'category_{category_id}')
                all_properties.append({
                    'category_id': category_id,
                    'category_name': category_name,
                    'annotation_id': annotation.get('id', 0),
                    'area': annotation.get('area', w * h)
                })
                
                # Add color
                color = color_map.get(category_id, (1.0, 1.0, 1.0, 1.0))
                all_colors.append(color)
            except Exception as e:
                print(f"Error processing bbox: {e}")
                continue
    
    if all_shapes:
        shapes_meta = {
            'properties': all_properties,
            'face_color': all_colors,
            'edge_color': all_colors,
            'shape_type': all_shape_types,
            'name': 'COCO Annotations'
        }
        layers.append((all_shapes, shapes_meta, 'shapes'))
    
    return layers