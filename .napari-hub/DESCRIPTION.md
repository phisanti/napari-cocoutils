# napari-cocoutils

A napari plugin for visualizing COCO annotation datasets with interactive controls.

## Features

- **Direct COCO Loading**: Load COCO JSON files directly into napari viewer
- **Category Management**: Toggle visibility of different annotation categories with checkboxes
- **Multi-Image Navigation**: Browse through datasets with multiple images
- **Performance Optimization**: N-filter to limit displayed annotations for large datasets  
- **Visualization Modes**: Switch between overlay and masked visualization modes
- **Proven Backend**: Built on the robust cocoutils library for reliable COCO data handling

## Usage

1. Install the plugin through napari's plugin manager or pip
2. Open napari and load your COCO JSON file using the plugin's reader
3. Use the COCO Controls widget to:
   - Filter annotations by category
   - Navigate between images in your dataset
   - Adjust visualization settings
   - Control the number of displayed annotations

## Requirements

- napari >= 0.6.4
- Python >= 3.10
- cocoutils library

Perfect for computer vision researchers who need to visualize and validate COCO annotation datasets interactively within the napari ecosystem.