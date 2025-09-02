# napari-cocoutils

A napari plugin for visualizing COCO annotation datasets with interactive controls and advanced filtering capabilities.

![PyPI - Version](https://img.shields.io/pypi/v/napari-cocoutils)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/napari-cocoutils)
![License](https://img.shields.io/github/license/yourusername/napari-cocoutils)

## Features

✨ **Interactive COCO Visualization**: Load and visualize COCO JSON annotation files directly in napari  
🎛️ **Advanced Filtering**: Filter annotations by category with real-time updates  
🔢 **Performance Controls**: N-filter sampling for handling large datasets (6K+ annotations)  
🖼️ **Multi-Image Support**: Navigate between images in datasets with multiple images  
⚡ **High Performance**: Optimized for large COCO files with thousands of annotations  
🎨 **Smart Color Coding**: Automatic category-based color assignment  
📊 **Rich Metadata**: View annotation properties, areas, and category information  

## Installation

### Requirements

- Python 3.10+
- napari 0.6.4+
- cocoutils (local dependency)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/napari-cocoutils.git
cd napari-cocoutils

# Create conda environment (recommended)
conda create -n cocoutils python=3.10
conda activate cocoutils

# Install dependencies
conda install -c conda-forge napari pyqt

# Install cocoutils dependency (adjust path as needed)
pip install -e /path/to/cocoutils

# Install the plugin in development mode
pip install -e .

# Optional: Install development dependencies
pip install -e ".[dev]"
```

### Quick Test Installation

```bash
# Activate the cocoutils environment
conda activate cocoutils

# Test the plugin installation
python -c "import napari_cocoutils; print('✓ Installation successful')"
```

## Usage

### Method 1: napari File Browser

1. Launch napari:
   ```bash
   napari
   ```

2. Open a COCO file:
   - Go to `File > Open Files...`
   - Navigate to your COCO JSON file
   - Select and open - napari will auto-detect the COCO format
   - Annotations will appear as colored shapes

### Method 2: Interactive Widget

1. Launch napari with the plugin:
   ```bash
   napari --plugin napari-cocoutils
   ```

2. Open the COCO Controls widget:
   - Go to `Plugins > napari-cocoutils: COCO Controls`
   - Use the interactive control panel on the right

3. Load and explore your data:
   - Click **Browse** to select a COCO JSON file
   - Use **category checkboxes** to filter annotations
   - Adjust **N-filter** for performance with large datasets
   - Navigate between **multiple images** if available

### Method 3: Python Script

```python
import napari
from napari_cocoutils import coco_reader

# Load COCO data
layers = coco_reader('path/to/your/coco_file.json')

# Launch napari
viewer = napari.Viewer()
for data, meta, layer_type in layers:
    if layer_type == 'shapes':
        viewer.add_shapes(data, **meta)

napari.run()
```

## Widget Interface

The interactive widget provides comprehensive controls:

```
┌─ COCO Controls ─────────────────────────────┐
│                                             │
├─ File Input ────────────────────────────────┤
│ [your_file.json               ] [Browse]    │
│ ✓ Loaded: 6145 annotations, 2 images       │
├─────────────────────────────────────────────┤
│                                             │
├─ Category Filters ──────────────────────────┤
│ [Select All] [Select None]                  │
│ ☑ cell (4069)                              │
│ ☑ clump (1685)                             │
│ ☑ noise (218)                              │
│ ☑ off-focus (102)                          │
│ ☑ joint cell (71)                          │
├─────────────────────────────────────────────┤
│                                             │
├─ Display Options ───────────────────────────┤
│ Max annotations: [1000] / 6145 visible     │
├─────────────────────────────────────────────┤
│                                             │
├─ Visualization Mode ────────────────────────┤
│ ● Overlay   ○ Masked                        │
├─────────────────────────────────────────────┤
│                                             │
├─ Multi-Image Navigation ────────────────────┤
│ Image: [1: frame_223.tiff          ▼]      │
│ [← Previous] [Next →]                       │
└─────────────────────────────────────────────┘
```

## Performance Tips

For large COCO datasets (5K+ annotations):

1. **Use N-filter**: Set to ~500-1000 annotations for smooth interaction
2. **Filter by category**: Uncheck unnecessary categories to reduce rendering load
3. **Progressive loading**: The plugin shows progress indicators for large files
4. **Memory optimization**: Built-in memory management prevents crashes

## Supported COCO Features

### Annotation Types
- ✅ **Polygons**: Complex segmentation masks with 3+ points
- ✅ **Bounding Boxes**: Rectangular annotations  
- ✅ **Mixed datasets**: Files with both polygon and bbox annotations

### Data Structure
- ✅ **Multiple images**: Navigate between images in the dataset
- ✅ **Multiple categories**: Color-coded with interactive filtering
- ✅ **Rich metadata**: Access annotation IDs, areas, category names
- ✅ **Large datasets**: Tested with 6K+ annotations

### Not Yet Supported
- ❌ **Image loading**: Must manually load corresponding images
- ❌ **Keypoints**: Point annotations not yet implemented  
- ❌ **RLE masks**: Run-length encoded masks
- ❌ **Panoptic segmentation**: Instance + semantic segmentation

## Examples

### Basic Visualization
```python
import napari
from napari_cocoutils import coco_reader

# Load COCO annotations
layers = coco_reader('annotations.json')

# Create napari viewer  
viewer = napari.Viewer()
for data, metadata, layer_type in layers:
    viewer.add_shapes(data, **metadata)

# Optionally load background image
viewer.open('background_image.jpg')

napari.run()
```

### Programmatic Filtering
```python
from napari_cocoutils import CocoWidget
import napari

viewer = napari.Viewer()
widget = CocoWidget(viewer)

# Load file
widget.file_manager.load_file('data.json')

# Initialize controllers
widget.category_controller.initialize_categories(widget.file_manager.coco_data)

# Filter to show only 'cell' category
widget.category_controller.select_none()
cell_id = 1  # Assuming 'cell' has ID 1
widget.category_controller.toggle_category(cell_id, True)
```

## Development

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test suites
python -m pytest tests/test_reader.py -v
python -m pytest tests/test_performance.py -v
python -m pytest tests/test_integration.py -v

# Run with coverage
python -m pytest --cov=napari_cocoutils
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
flake8 .
```

## Troubleshooting

### Common Issues

**"No module named napari_cocoutils"**
```bash
# Ensure plugin is installed correctly
pip install -e .
# Restart napari after installation
```

**"No module named cocoutils"**  
```bash
# Install the cocoutils dependency
pip install -e /path/to/cocoutils
```

**"napari doesn't recognize COCO files"**
```bash
# Restart napari after plugin installation
# Ensure file has .json extension
```

**"Annotations appear but no background image"**
- The plugin loads annotations only
- Manually load corresponding images: `File > Open Files...`

### Performance Issues

**Large datasets slow to load**
- Use the N-filter to limit displayed annotations
- Filter by category to reduce data size
- Check console for progress indicators

**Memory usage high**
- Clear napari layers periodically
- Use built-in memory optimization features
- Consider processing subsets of large datasets

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution
- 🖼️ Direct image loading from COCO files
- 🔑 Keypoint annotation support
- 🎨 Custom visualization modes
- 📊 Advanced statistics and analytics
- 🔧 Performance optimizations

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use napari-cocoutils in your research, please cite:

```bibtex
@software{napari_cocoutils,
  title={napari-cocoutils: Interactive COCO Annotation Visualization},
  url={https://github.com/yourusername/napari-cocoutils},
  year={2024}
}
```

## Acknowledgments

- Built on the powerful [napari](https://napari.org) visualization framework
- Integrates with the [cocoutils](https://github.com/yourusername/cocoutils) library
- Inspired by the [COCO dataset](https://cocodataset.org) format
