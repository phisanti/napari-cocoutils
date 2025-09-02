"""
Core visualization logic for COCO data in napari.

This module handles the conversion of COCO annotation data into napari-compatible
formats and provides utilities for rendering different visualization modes.
Adapts the cocoutils visualization logic for napari's layer system.
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from napari.types import LayerDataTuple

from ._config import get_effective_config
from ._memory import get_memory_manager, LRUCache


class CocoNapariVisualizer:
    """
    Handles visualization of COCO data in napari format.
    
    This class bridges between cocoutils visualization logic and napari's
    layer system, providing methods to convert COCO data into appropriate
    napari layer formats with proper styling and interaction.
    """
    
    def __init__(self, coco_data: Dict[str, Any]):
        """
        Initialize visualizer with COCO data.
        
        Parameters
        ----------
        coco_data : dict
            Loaded COCO JSON data structure
        """
        self.coco_data = coco_data
        self.categories = {cat['id']: cat for cat in coco_data.get('categories', [])}
        self.images = {img['id']: img for img in coco_data.get('images', [])}
        self.annotations = coco_data.get('annotations', [])
        
        # Pre-compute lookup arrays for vectorized filtering - critical for large datasets
        self.ann_image_ids = np.array([ann.get('image_id', 0) for ann in self.annotations], dtype=np.int32)
        self.ann_category_ids = np.array([ann.get('category_id', 0) for ann in self.annotations], dtype=np.int32)
        
        self.category_counts = self._compute_category_counts()
        self.category_colors = self._generate_category_colors()
        
        self.config = get_effective_config()
        
        memory_manager = get_memory_manager()
        self._annotation_cache = memory_manager.get_cache("annotations", 50, 25)
        self._shape_cache = memory_manager.get_cache("shapes", 20, 100)  
        self._polygon_cache = memory_manager.get_cache("polygons", 1000, 50)
        self._bbox_cache = memory_manager.get_cache("bboxes", 1000, 10)
        
        memory_manager.register_object(self, self._cleanup_callback)
    
    
    def create_shapes_layer(self, image_id: int, 
                          category_filter: Optional[List[int]] = None,
                          show_bbox: bool = True,
                          show_mask: bool = True,
                          n_filter: Optional[int] = None,
                          random_seed: int = 42) -> Optional[LayerDataTuple]:
        """
        Create napari shapes layer for annotations of specified image.
        
        Parameters
        ----------
        image_id : int
            COCO image ID to create annotation shapes for
        category_filter : list of int, optional
            List of category IDs to include, or None for all categories
        show_bbox : bool, optional
            Whether to include bounding box annotations
        show_mask : bool, optional
            Whether to include mask/polygon annotations
        n_filter : int, optional
            Maximum number of annotations to display (for performance)
        random_seed : int, optional
            Random seed for consistent sampling
            
        Returns
        -------
        LayerDataTuple or None
            Napari shapes layer data tuple, or None if no annotations
        """
        cache_key = (image_id, tuple(sorted(category_filter)) if category_filter else None, show_bbox, show_mask, n_filter, random_seed)
        
        cached_result = self._shape_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        annotations = self._get_selected_annotations(image_id, category_filter)
        
        if not annotations:
            self._shape_cache.put(cache_key, None, 0)
            return None
        
        # Apply N-filter sampling at annotation level (before shape conversion)
        if n_filter and len(annotations) > n_filter:
            annotations = self.subsample_annotations(annotations, n_filter, random_seed)
            print(f"N-filter applied: {len(annotations)} annotations sampled from original total")
        
        shapes_data = []
        properties = []
        face_colors = []
        edge_colors = []
        shape_types = []
        
        for annotation in annotations:
            category_id = annotation.get('category_id', 1)
            category_name = self.categories.get(category_id, {}).get('name', f'category_{category_id}')
            
            if show_mask and 'segmentation' in annotation and annotation['segmentation']:
                for seg in annotation['segmentation']:
                    if len(seg) >= 6:
                        napari_shape = self._convert_polygon_cached(seg)
                        if napari_shape is not None:
                            shapes_data.append(napari_shape)
                            shape_types.append('polygon')
                            color = self.category_colors.get(category_id, (1.0, 1.0, 1.0, 1.0))
                            face_colors.append(color)  # Masks have filled faces
                            edge_colors.append(color)
                            properties.append({
                                'category_id': category_id,
                                'category_name': category_name,
                                'annotation_id': annotation.get('id', 0),
                                'area': annotation.get('area', 0),
                                'type': 'mask'
                            })
            
            if show_bbox and 'bbox' in annotation:
                napari_shape = self._convert_bbox_cached(annotation['bbox'])
                if napari_shape is not None:
                    shapes_data.append(napari_shape)
                    # When both bbox and mask are shown, convert bbox to polygon for consistency
                    if show_mask:
                        shape_types.append('polygon')
                    else:
                        shape_types.append('rectangle')
                    color = self.category_colors.get(category_id, (1.0, 1.0, 1.0, 1.0))
                    face_colors.append((0.0, 0.0, 0.0, 0.0))  # Transparent face for bboxes
                    edge_colors.append(color)  # Colored border
                    properties.append({
                        'category_id': category_id,
                        'category_name': category_name,
                        'annotation_id': annotation.get('id', 0),
                        'area': annotation.get('area', 0),
                        'type': 'bbox'
                    })
        
        if not shapes_data:
            result = None
        else:
            # Ensure consistent shape types - convert all to polygons if mixed types exist
            if show_bbox and show_mask and len(set(shape_types)) > 1:
                print("Converting all shapes to polygons for consistent display")
                for i, shape_type in enumerate(shape_types):
                    if shape_type == 'rectangle':
                        shape_types[i] = 'polygon'
            
            layer_kwargs = {
                'properties': properties,
                'face_color': face_colors,
                'edge_color': edge_colors,
                'shape_type': shape_types,
                'edge_width': 2,
                'face_color_cycle': None,
                'edge_color_cycle': None
            }
            result = (shapes_data, layer_kwargs, 'shapes')
        
        estimated_size = len(shapes_data) * 1024 if shapes_data else 0
        self._shape_cache.put(cache_key, result, estimated_size)
        return result
    
    
    def get_category_colors(self) -> Dict[int, Tuple[float, float, float, float]]:
        """
        Get color mapping for COCO categories.
        
        Returns
        -------
        dict
            Mapping from category ID to RGBA color tuple
        """
        return self.category_colors
    
    
    def _get_selected_annotations(self, image_id: int, category_filter: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Get selected annotations for specified image and categories with caching.
        
        Parameters
        ----------
        image_id : int
            COCO image ID to filter annotations for
        category_filter : list of int, optional
            List of category IDs to include, or None for all categories
            
        Returns
        -------
        list of dict
            Selected COCO annotation dictionaries
        """
        cache_key = (image_id, tuple(sorted(category_filter)) if category_filter else None)
        
        cached_annotations = self._annotation_cache.get(cache_key)
        if cached_annotations is not None:
            return cached_annotations
        
        # Vectorized filtering is essential for performance with large datasets
        mask = (self.ann_image_ids == image_id)
        if category_filter:
            mask &= np.isin(self.ann_category_ids, category_filter)
        
        indices = np.where(mask)[0]
        annotations = [self.annotations[i] for i in indices]
        
        estimated_size = len(annotations) * 200
        self._annotation_cache.put(cache_key, annotations, estimated_size)
        return annotations
    
    def subsample_annotations(self, annotations: List[Dict[str, Any]], sample_size: int, random_seed: int = 42) -> List[Dict[str, Any]]:
        """
        Subsample annotations to the specified sample size using random sampling.
        
        This method applies N-filter logic at the annotation level, ensuring that
        when an annotation is selected, all its shapes (bbox + polygons) will be
        included together in the final visualization.
        
        Parameters
        ----------
        annotations : list of dict
            List of COCO annotation dictionaries to subsample from
        sample_size : int
            Maximum number of annotations to select
        random_seed : int, optional
            Random seed for consistent sampling (default: 42)
            
        Returns
        -------
        list of dict
            Subsampled list of COCO annotation dictionaries
        """
        if sample_size >= len(annotations):
            # No subsampling needed
            return annotations
        
        rng = np.random.RandomState(random_seed)
        sample_size = min(sample_size, len(annotations))
        indices = rng.choice(len(annotations), sample_size, replace=False)
        
        # Return subsampled annotations in original order
        indices = np.sort(indices)
        return [annotations[i] for i in indices]
    
    def _convert_polygon_cached(self, polygon: List[float]) -> Optional[np.ndarray]:
        """
        Convert COCO polygon to napari format with caching for performance.
        
        Parameters
        ----------
        polygon : list of float
            COCO polygon coordinates [x1, y1, x2, y2, ...]
            
        Returns
        -------
        numpy.ndarray or None
            Napari polygon points array or None if conversion fails
        """
        # Use hash as cache key - acceptable collision risk for performance gain
        cache_key = hash(tuple(polygon))
        
        cached_polygon = self._polygon_cache.get(cache_key)
        if cached_polygon is not None:
            return cached_polygon
        
        result = self.convert_coco_polygon_to_napari([polygon])
        estimated_size = len(polygon) * 8 if polygon else 0
        self._polygon_cache.put(cache_key, result, estimated_size)
        return result
    
    def _convert_bbox_cached(self, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Convert COCO bounding box to napari format with caching for performance.
        
        Parameters
        ----------
        bbox : list of float
            COCO bounding box [x, y, width, height]
            
        Returns
        -------
        numpy.ndarray or None
            Napari rectangle corner points or None if conversion fails
        """
        cache_key = tuple(bbox)
        
        cached_bbox = self._bbox_cache.get(cache_key)
        if cached_bbox is not None:
            return cached_bbox
        
        result = self.convert_coco_bbox_to_napari(bbox)
        self._bbox_cache.put(cache_key, result, 64)
        return result
    
    def clear_cache(self):
        """Clear all visualization caches to free memory."""
        self._annotation_cache.clear()
        self._shape_cache.clear()
        self._polygon_cache.clear()
        self._bbox_cache.clear()
    
    def _cleanup_callback(self):
        """Callback for memory management cleanup."""
        self.clear_cache()
    
    def convert_coco_polygon_to_napari(self, segmentation: List[List[float]]) -> Optional[np.ndarray]:
        """
        Convert COCO polygon segmentation to napari shapes format.
        
        Parameters
        ----------
        segmentation : list of list of float
            COCO polygon segmentation data
            
        Returns
        -------
        numpy.ndarray or None
            Polygon points in napari shapes format (N, 2), or None if invalid
        """
        if not segmentation or not segmentation[0]:
            return None
        
        # Take the first polygon (COCO can have multiple polygons per annotation)
        polygon = segmentation[0]
        
        if len(polygon) < 6:  # COCO polygon format: [x1,y1,x2,y2,x3,y3,...] minimum 3 points
            return None
        
        try:
            # Pre-allocate for performance - avoids memory reallocation
            n_points = len(polygon) // 2
            napari_points = np.empty((n_points, 2), dtype=np.float64)
            
            # Direct slice assignment avoids temporary arrays
            napari_points[:, 1] = polygon[0::2]  # COCO x -> napari col  
            napari_points[:, 0] = polygon[1::2]  # COCO y -> napari row
            return napari_points
        except Exception:
            return None
    
    def convert_coco_bbox_to_napari(self, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Convert COCO bounding box to napari rectangle format.
        
        Parameters
        ----------
        bbox : list of float
            COCO bounding box [x, y, width, height]
            
        Returns
        -------
        numpy.ndarray or None
            Rectangle corners in napari format (4, 2), or None if invalid
        """
        if len(bbox) < 4:
            return None
        
        try:
            x, y, w, h = bbox
            corners = np.array([
                [y, x],           # top-left
                [y, x + w],       # top-right  
                [y + h, x + w],   # bottom-right
                [y + h, x]        # bottom-left
            ])
            return corners
        except Exception:
            return None
    
    
    def _generate_category_colors(self) -> Dict[int, Tuple[float, float, float, float]]:
        """
        Generate colors for categories using vectorized approach for performance.
        
        Returns
        -------
        dict
            Mapping from category ID to RGBA color tuple
        """
        num_categories = len(self.categories)
        if num_categories == 0:
            return {}
        
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            # Fallback when matplotlib unavailable
            return {cat_id: (1.0, 0.0, 0.0, 1.0) for cat_id in self.categories}
        
        # tab20 provides better visual distinction for small category counts
        cmap_name = 'tab20' if num_categories <= 20 else 'hsv'
        cmap = plt.colormaps.get_cmap(cmap_name)
        
        # Vectorized generation avoids Python loops
        if num_categories <= 20:
            indices = np.arange(num_categories)
        else:
            indices = np.linspace(0, 1, num_categories, endpoint=False)
        
        colors = cmap(indices)
        sorted_cat_ids = sorted(self.categories.keys())
        return {cat_id: tuple(colors[i]) for i, cat_id in enumerate(sorted_cat_ids)}
    
    def _compute_category_counts(self) -> Dict[int, int]:
        """
        Pre-compute category annotation counts for fast UI updates.
        
        Returns
        -------
        dict
            Mapping from category ID to annotation count
        """
        if len(self.annotations) == 0:
            return {}
        
        # Vectorized counting is much faster than Python loops for large datasets
        unique_ids, counts = np.unique(self.ann_category_ids, return_counts=True)
        category_counts = dict(zip(unique_ids, counts))
        
        # Ensure all categories are represented for consistent UI
        for cat_id in self.categories:
            if cat_id not in category_counts:
                category_counts[cat_id] = 0
        
        return category_counts
    
    def get_category_count(self, category_id: int) -> int:
        """
        Get annotation count for a specific category (cached for performance).
        
        Parameters
        ----------
        category_id : int
            Category ID to get count for
            
        Returns
        -------
        int
            Number of annotations for this category
        """
        return self.category_counts.get(category_id, 0)