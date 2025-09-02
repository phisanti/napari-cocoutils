# CocoUtils Integration Primer for napari-cocoutils Plugin

This document provides essential information about the cocoutils library to help agents building the napari-cocoutils plugin understand the key components and integration points.

## 1. Core cocoutils Architecture

### Key Modules Overview
```
cocoutils/
├── cli.py                  # Main command-line interface
├── visualise/
│   └── visualizer.py      # CocoVisualizer - PRIMARY INTEGRATION TARGET
├── utils/
│   ├── categories.py      # CategoryManager - handles category metadata
│   ├── geometry.py        # Polygon/mask utilities
│   └── io.py             # COCO JSON I/O functions
├── convert/               # TIFF → COCO conversion
├── reconstruct/           # COCO → TIFF reconstruction  
├── merge/                 # Merge multiple COCO files
└── split/                 # Split COCO into per-image files
```

### Data Flow Architecture
1. **Load**: `io.load_coco()` → COCO JSON structure
2. **Process**: Category filtering, annotation selection
3. **Visualize**: `CocoVisualizer` → matplotlib rendering
4. **Export**: Various formats (TIFF masks, JSON, etc.)

---

## 2. Most Important Parts for Plugin Development

### A. CocoVisualizer (PRIMARY CLASS)
**Location**: `cocoutils.visualise.visualizer.CocoVisualizer`

**Key Properties:**
```python
self.coco: COCO                           # pycocotools COCO object
self.cat_ids: List[int]                   # Available category IDs
self.cats: List[Dict]                     # Category metadata
self.catid_to_color: Dict[int, tuple]     # ID → RGBA color mapping
```

**Essential Methods for Plugin:**
1. **`__init__(coco_file: str)`**
   - Initializes with COCO JSON file path
   - Sets up category colors automatically
   - Creates `pycocotools.COCO` instance

2. **`visualize(image_path, image_id=None, ann_ids=None, show_masks=True, show_bboxes=True, show_class_names=True)`**
   - Main visualization method
   - Can filter specific annotations with `ann_ids`
   - Handles category-based coloring automatically
   - Returns matplotlib visualization

3. **`visualize_annotations_masked(image, annotation_ids, ax=None)`**
   - **CRITICAL FOR PLUGIN**: Masked visualization mode
   - Sets background pixels to 0 for selected annotations
   - Uses `create_segmentation_mask` for proper hole handling
   - Perfect for napari labels layer integration

### B. Category Management System
**Location**: `cocoutils.utils.categories.CategoryManager`

**Key Features:**
- Bidirectional ID ↔ name mapping
- Duplicate validation
- JSON-based category definitions

**Integration Points:**
```python
# Access category info via CocoVisualizer
visualizer.cats                    # List of category dicts
visualizer.cat_ids                 # List of category IDs  
visualizer.catid_to_color          # Color mapping
```

### C. Geometry Utilities
**Location**: `cocoutils.utils.geometry`

**Key Functions:**
1. **`create_segmentation_mask(segmentation, segmentation_types, img_height, img_width)`**
   - **ESSENTIAL**: Converts COCO polygons to binary masks
   - Handles holes and multi-part segmentations correctly  
   - Returns torch.Tensor mask
   - Use this for napari labels layer

2. **`determine_polygon_orientation(polygon)`**
   - Distinguishes positive areas (1) from holes (0)
   - Uses signed area calculation

### D. I/O Utilities
**Location**: `cocoutils.utils.io`

**Key Functions:**
1. **`load_coco(path: str) → Dict[str, Any]`**
   - Validates COCO JSON structure
   - Handles errors gracefully
   - **Use this instead of raw JSON loading**

2. **`save_coco(obj: Dict[str, Any], path: str)`**
   - Atomic file writing
   - Error handling

---

## 3. Integration Strategy for napari Plugin

### Phase 1: Basic Reader Integration
```python
# In coco_reader.py
from cocoutils.utils.io import load_coco
from cocoutils.visualise.visualizer import CocoVisualizer

def coco_reader(path):
    try:
        coco_data = load_coco(path)          # Validated loading
        visualizer = CocoVisualizer(path)     # Color setup
        return convert_to_napari_layers(coco_data, visualizer)
    except (ValueError, FileNotFoundError):
        return None
```

### Phase 2: Widget Integration  
```python
# In coco_widget.py
class CocoWidget:
    def __init__(self, viewer):
        self.viewer = viewer
        self.visualizer = None               # CocoVisualizer instance
        self.current_image_id = None
        
    def load_coco_file(self, path):
        self.visualizer = CocoVisualizer(path)
        self._update_category_controls()     # Use visualizer.cats
        
    def filter_by_categories(self, selected_cat_ids):
        ann_ids = self.visualizer.coco.getAnnIds(
            imgIds=[self.current_image_id], 
            catIds=selected_cat_ids
        )
        self._update_visualization(ann_ids)
```

### Phase 3: Advanced Visualization
```python
# Use masked visualization for special display modes
def create_masked_layer(self, image_array, annotation_ids):
    return self.visualizer.visualize_annotations_masked(
        image=image_array,
        annotation_ids=annotation_ids,
        ax=None,  # Don't create matplotlib figure
        show=False
    )
```

---

## 4. Key COCO Data Structures (via pycocotools)

### Accessing Data
```python
visualizer = CocoVisualizer(coco_file)

# Categories
categories = visualizer.cats                    # [{'id': 1, 'name': 'cell'}, ...]
category_ids = visualizer.cat_ids              # [1, 2, 3, ...]

# Images  
image_ids = visualizer.coco.getImgIds()        # All image IDs
image_info = visualizer.coco.loadImgs([img_id])[0]  # {'id': 1, 'file_name': 'img.jpg', 'height': 512, 'width': 512}

# Annotations
ann_ids = visualizer.coco.getAnnIds(imgIds=[image_id])           # All annotations for image
ann_ids_filtered = visualizer.coco.getAnnIds(                   # Filtered annotations
    imgIds=[image_id], 
    catIds=[1, 2]
)
annotations = visualizer.coco.loadAnns(ann_ids)                 # Load annotation objects
```

### Annotation Structure
```python
annotation = {
    'id': 123,
    'image_id': 456,
    'category_id': 1,
    'segmentation': [[x1, y1, x2, y2, ...]],     # Polygon coordinates
    'bbox': [x, y, width, height],                # Bounding box
    'area': 1234.5,
    'iscrowd': 0
}
```

---

## 5. Critical Integration Points

### A. Color Consistency
**ALWAYS use CocoVisualizer's color mapping:**
```python
color = visualizer.catid_to_color[category_id]  # RGBA tuple (0-1 range)
```

### B. Coordinate Systems
- **COCO format**: `[x, y, width, height]` for bbox, `[x1, y1, x2, y2, ...]` for polygons
- **napari format**: `[[row, col], [row, col], ...]` (note: row=y, col=x)
- **Convert carefully** between systems

### C. Mask Generation
**Always use cocoutils geometry utilities:**
```python
from cocoutils.utils.geometry import create_segmentation_mask

mask = create_segmentation_mask(
    annotation['segmentation'],
    None,  # Will auto-detect orientation
    image_height,
    image_width
)
```

### D. Error Handling
Follow cocoutils patterns:
```python
try:
    coco_data = load_coco(path)
except (ValueError, FileNotFoundError) as e:
    # Handle gracefully
    return None
```

---

## 6. Performance Considerations

### A. Lazy Loading
- CocoVisualizer loads all data on init
- For large datasets, consider caching strategies
- Load annotations per-image as needed

### B. Memory Management  
- Use `create_segmentation_mask` for efficient mask generation
- Clear matplotlib figures in masked visualization
- Consider downsampling for very large images

### C. Batch Operations
```python
# Efficient: Load multiple annotations at once
ann_ids = visualizer.coco.getAnnIds(imgIds=[image_id], catIds=selected_categories)
annotations = visualizer.coco.loadAnns(ann_ids)

# Inefficient: Load one by one
# for ann_id in ann_ids: visualizer.coco.loadAnns([ann_id])
```

---

## 7. Plugin-Specific Adaptations

### A. Converting to napari Shapes
```python
def coco_polygon_to_napari_shape(polygon_coords):
    """Convert COCO [x1,y1,x2,y2,...] to napari [[y1,x1],[y2,x2],...]"""
    coords = np.array(polygon_coords).reshape(-1, 2)  # [[x1,y1],[x2,y2],...]
    return coords[:, [1, 0]]  # Swap to [[y1,x1],[y2,x2],...] for napari
```

### B. Category Filtering UI
```python
def get_unique_categories_in_image(self, image_id):
    """Get categories present in specific image for UI filtering"""
    ann_ids = self.visualizer.coco.getAnnIds(imgIds=[image_id])
    annotations = self.visualizer.coco.loadAnns(ann_ids)
    cat_ids = list(set(ann['category_id'] for ann in annotations))
    return [(cat_id, self.visualizer.coco.loadCats([cat_id])[0]['name']) 
            for cat_id in cat_ids]
```

This primer provides the essential knowledge needed to integrate cocoutils effectively with the napari plugin architecture.