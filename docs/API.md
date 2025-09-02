# API Documentation

Complete API reference for napari-cocoutils plugin.

## Core Functions

### Reader Functions

#### `coco_reader(path: Union[str, List[str]]) -> Optional[List[LayerDataTuple]]`

Main napari reader hook for COCO JSON files.

**Parameters:**
- `path` (str or list): Path to COCO JSON file(s) to read

**Returns:**
- `List[LayerDataTuple]` or `None`: napari-compatible layer data tuples, or None if file cannot be read

**Example:**
```python
from napari_cocoutils import coco_reader

# Load COCO data
layers = coco_reader('annotations.json')
for data, metadata, layer_type in layers:
    print(f"Layer type: {layer_type}, Shapes: {len(data)}")
```

### Utility Functions

#### `load_coco_file(file_path: Union[str, Path]) -> Dict[str, Any]`

Load and validate a COCO JSON file using cocoutils integration.

**Parameters:**
- `file_path` (str or Path): Path to COCO JSON file

**Returns:**
- `Dict[str, Any]`: Loaded COCO data dictionary

**Raises:**
- `CocoError`: If file cannot be loaded or has invalid format

#### `validate_coco_structure(data: Optional[Dict[str, Any]]) -> bool`

Validate that dictionary contains valid COCO structure.

**Parameters:**  
- `data` (dict): Dictionary to validate as COCO format

**Returns:**
- `bool`: True if valid COCO structure, False otherwise

#### `convert_coco_to_napari_coordinates(polygon: List[float]) -> np.ndarray`

Convert COCO polygon coordinates to napari format.

**Parameters:**
- `polygon` (list of float): COCO polygon in [x1, y1, x2, y2, ...] format

**Returns:**
- `np.ndarray`: napari shape points in (N, 2) format [row, col]

#### `generate_category_colors(num_categories: int) -> List[Tuple[float, float, float, float]]`

Generate distinct colors for categories.

**Parameters:**
- `num_categories` (int): Number of distinct colors needed

**Returns:**
- `List[Tuple]`: RGBA color tuples (values 0-1) for napari compatibility

## Widget Classes

### CocoWidget

Main interactive widget for COCO visualization controls.

#### `__init__(self, viewer: napari.Viewer)`

Initialize COCO widget with napari viewer.

**Parameters:**
- `viewer` (napari.Viewer): napari viewer instance

#### Key Methods

##### `on_file_selected(self) -> None`
Handle file selection via browse dialog.

##### `_refresh_visualization(self) -> None`
Update napari visualization with current settings.

##### `_update_category_controls(self) -> None`
Update category checkboxes based on loaded data.

## Controller Classes

### CocoFileManager

Manages COCO file loading and data access.

#### Methods

##### `load_file(self, file_path: str) -> Dict[str, Any]`
Load COCO file and store data.

##### `get_file_info(self) -> Dict[str, Any]`
Get summary information about loaded file.

##### `is_loaded(self) -> bool`
Check if COCO data is currently loaded.

### CategoryController

Manages category filtering and color assignment.

#### Methods

##### `initialize_categories(self, coco_data: Dict[str, Any]) -> None`
Initialize categories from COCO data.

##### `toggle_category(self, category_id: int, enabled: bool) -> None`
Enable/disable specific category.

##### `get_selected_categories(self) -> List[int]`
Get list of currently selected category IDs.

##### `get_category_color(self, category_id: int) -> Tuple[float, float, float, float]`
Get RGBA color for specified category.

### NavigationController

Handles multi-image dataset navigation.

#### Methods

##### `initialize_images(self, coco_data: Dict[str, Any]) -> None`
Initialize image list from COCO data.

##### `get_current_image(self) -> Optional[Dict[str, Any]]`
Get current image information.

##### `navigate_to_image(self, image_idx: int) -> bool`
Navigate to specific image index.

##### `has_multiple_images(self) -> bool`
Check if dataset contains multiple images.

### VisualizationManager

Manages napari layer creation and updates.

#### Methods

##### `initialize_visualizer(self, coco_data: Dict[str, Any]) -> None`
Initialize visualization components with COCO data.

##### `refresh_visualization(self, image_id: int, selected_categories: List[int], ...) -> None`
Update napari visualization with current filters.

##### `cleanup(self) -> None`
Clean up napari layers and resources.

### DisplayController

Controls display options and annotation filtering.

#### Methods

##### `set_n_filter(self, value: int) -> None`
Set maximum number of annotations to display.

##### `set_visualization_mode(self, mode: str) -> None`
Set visualization mode ('overlay' or 'masked').

##### `get_annotation_count_info(self, coco_data: Dict[str, Any], image_id: int, selected_categories: List[int]) -> Dict[str, int]`
Get annotation count information for current settings.

## Error Classes

### CocoError

Custom exception for COCO-related errors.

#### `__init__(self, message: str, user_message: Optional[str] = None)`

**Parameters:**
- `message` (str): Technical error message
- `user_message` (str, optional): User-friendly error message

## Configuration

### Memory Management

#### `get_memory_manager() -> MemoryManager`
Get global memory manager instance for cache and resource management.

#### `configure_memory_management(gc_threshold: int = 50) -> None`
Configure memory management parameters.

### Progress Reporting

#### `progress_context(title: str, reporter_type: str = "auto", parent=None)`
Context manager for progress reporting during long operations.

**Parameters:**
- `title` (str): Progress dialog title
- `reporter_type` (str): "auto", "console", or "qt"
- `parent`: Parent widget for Qt dialogs

**Example:**
```python
from napari_cocoutils._progress import progress_context

with progress_context("Loading data...") as reporter:
    for i in range(total_items):
        # Do work
        reporter.update(i, total_items, f"Processing item {i}")
```

## Type Definitions

### LayerDataTuple
```python
LayerDataTuple = Tuple[Any, Dict[str, Any], str]
# (layer_data, metadata, layer_type)
```

### COCO Data Structures

#### CocoAnnotation (Protocol)
```python
class CocoAnnotation(Protocol):
    id: int
    image_id: int
    category_id: int
    area: Optional[float]
    bbox: Optional[List[float]]
    segmentation: Optional[List[List[float]]]
```

#### CocoCategory (Protocol)  
```python
class CocoCategory(Protocol):
    id: int
    name: str
    supercategory: Optional[str]
```

#### CocoImage (Protocol)
```python
class CocoImage(Protocol):
    id: int
    file_name: str
    width: int
    height: int
```

## Constants

### Default Values
- `DEFAULT_N_FILTER = 1000`: Default maximum annotations to display
- `DEFAULT_VISUALIZATION_MODE = "overlay"`: Default visualization mode
- `DEFAULT_EDGE_WIDTH = 1`: Default edge width for shapes

### Performance Limits
- `MAX_ANNOTATIONS_WITHOUT_FILTER = 5000`: Threshold for auto-enabling N-filter
- `PROGRESS_UPDATE_INTERVAL = 100`: Update progress every N annotations

## Examples

### Basic Usage
```python
import napari
from napari_cocoutils import coco_reader, CocoWidget

# Method 1: Direct reader usage
viewer = napari.Viewer()
layers = coco_reader('data.json')
for data, meta, layer_type in layers:
    viewer.add_shapes(data, **meta)

# Method 2: Widget usage
widget = CocoWidget(viewer)
# Widget provides interactive controls
```

### Advanced Filtering
```python
from napari_cocoutils._controllers import (
    CocoFileManager, CategoryController, DisplayController
)

# Load data
manager = CocoFileManager()
data = manager.load_file('annotations.json')

# Set up filtering
cat_controller = CategoryController()
cat_controller.initialize_categories(data)

# Filter to specific categories
cat_controller.select_none()
cat_controller.toggle_category(1, True)  # Enable category 1
cat_controller.toggle_category(3, True)  # Enable category 3

selected = cat_controller.get_selected_categories()
print(f"Selected categories: {selected}")
```

### Performance Monitoring
```python
from napari_cocoutils._memory import get_memory_stats
from napari_cocoutils._progress import console_progress

# Monitor memory usage
stats = get_memory_stats()
print(f"Cache entries: {stats.cache_entries}")
print(f"Memory usage: {stats.cache_size_bytes / 1024 / 1024:.1f} MB")

# Use progress reporting
with console_progress("Processing large dataset...") as reporter:
    for i in range(10000):
        # Simulate work
        if i % 1000 == 0:
            reporter.update(i, 10000, f"Processed {i} items")
```

## Plugin Integration

### napari Plugin Discovery

The plugin is discovered via `napari.yaml` manifest:

```yaml
name: napari-cocoutils
display_name: COCO Utils
contributions:
  commands:
    - id: napari-cocoutils.coco_reader
      python_name: napari_cocoutils._reader:coco_reader
      title: Read COCO JSON files
    - id: napari-cocoutils.coco_widget
      python_name: napari_cocoutils._widget:CocoWidget
      title: COCO Controls
  readers:
    - command: napari-cocoutils.coco_reader
      filename_patterns: ['*.json']
      accepts_directories: false
  widgets:
    - command: napari-cocoutils.coco_widget
      display_name: COCO Controls
```

### Extension Points

The plugin provides several extension points for customization:

1. **Custom Progress Reporters**: Implement `ProgressReporter` interface
2. **Memory Management**: Configure caching and GC strategies  
3. **Visualization Modes**: Extend `DisplayController` for new modes
4. **Data Loaders**: Extend `CocoFileManager` for custom formats