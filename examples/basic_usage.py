#!/usr/bin/env python3
"""
Basic usage example for napari-cocoutils plugin.

This script demonstrates how to load and visualize COCO annotation files
using the napari-cocoutils plugin in different ways.
"""

import napari
from pathlib import Path
import sys
import os

# Add src to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from napari_cocoutils import coco_reader
from napari_cocoutils._widget import CocoWidget

# Sample COCO file path (adjust as needed)
SAMPLE_COCO_FILE = "/Users/santiago/switchdrive/boeck_lab_projects/cocoutils/test.json"


def example_1_direct_reader():
    """Example 1: Direct use of coco_reader function."""
    print("Example 1: Direct reader usage")
    print("-" * 40)
    
    if not Path(SAMPLE_COCO_FILE).exists():
        print(f"⚠️  Sample file not found: {SAMPLE_COCO_FILE}")
        print("Please update SAMPLE_COCO_FILE path in the script")
        return
    
    # Load COCO data
    print(f"Loading COCO file: {SAMPLE_COCO_FILE}")
    layers = coco_reader(SAMPLE_COCO_FILE)
    
    if not layers:
        print("❌ Failed to load COCO file")
        return
    
    print(f"✅ Loaded {len(layers)} layer(s)")
    
    # Analyze the data
    shapes_data, metadata, layer_type = layers[0]
    num_shapes = len(shapes_data)
    categories = set(prop['category_name'] for prop in metadata['properties'])
    
    print(f"   - Layer type: {layer_type}")
    print(f"   - Number of shapes: {num_shapes}")
    print(f"   - Categories: {', '.join(sorted(categories))}")
    
    # Create napari viewer
    print("\n🖼️  Opening napari viewer...")
    viewer = napari.Viewer()
    
    # Add shapes layer
    layer = viewer.add_shapes(shapes_data, **metadata)
    print(f"✅ Added layer '{layer.name}' to viewer")
    
    # Show some statistics
    print(f"   - Face colors: {len(layer.face_color)} colors")
    print(f"   - Edge colors: {len(layer.edge_color)} colors")
    print(f"   - Properties: {len(layer.properties)} items")
    
    print("\n💡 Try these interactions in napari:")
    print("   - Click on shapes to see properties")
    print("   - Use zoom/pan to explore annotations")
    print("   - Toggle layer visibility")
    
    # Start napari (this will block until window is closed)
    napari.run()


def example_2_widget_usage():
    """Example 2: Using the interactive widget."""
    print("Example 2: Interactive widget usage")
    print("-" * 40)
    
    if not Path(SAMPLE_COCO_FILE).exists():
        print(f"⚠️  Sample file not found: {SAMPLE_COCO_FILE}")
        return
    
    # Create napari viewer
    viewer = napari.Viewer()
    
    # Create widget
    print("🎛️  Creating COCO widget...")
    widget = CocoWidget(viewer)
    
    # Add widget to viewer
    viewer.window.add_dock_widget(widget, area='right', name='COCO Controls')
    
    # Load file programmatically
    print(f"📂 Loading file: {SAMPLE_COCO_FILE}")
    try:
        widget.file_manager.load_file(SAMPLE_COCO_FILE)
        print("✅ File loaded successfully")
        
        # Initialize controllers
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Update UI
        widget._update_category_controls()
        widget._update_image_navigation()
        widget._refresh_visualization()
        
        # Show some info
        file_info = widget.file_manager.get_file_info()
        print(f"   - Annotations: {file_info['num_annotations']}")
        print(f"   - Images: {file_info['num_images']}")
        print(f"   - Categories: {file_info['num_categories']}")
        
        categories = widget.category_controller.categories
        print(f"   - Category names: {[cat['name'] for cat in categories.values()]}")
        
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    print("\n💡 Try these widget interactions:")
    print("   - Use category checkboxes to filter annotations")
    print("   - Adjust N-filter for performance")
    print("   - Navigate between images (if multiple)")
    print("   - Try different visualization modes")
    
    # Start napari
    napari.run()


def example_3_programmatic_filtering():
    """Example 3: Programmatic filtering without GUI."""
    print("Example 3: Programmatic filtering")
    print("-" * 40)
    
    if not Path(SAMPLE_COCO_FILE).exists():
        print(f"⚠️  Sample file not found: {SAMPLE_COCO_FILE}")
        return
    
    from napari_cocoutils._controllers import (
        CocoFileManager, CategoryController, DisplayController
    )
    
    # Load data
    file_manager = CocoFileManager()
    data = file_manager.load_file(SAMPLE_COCO_FILE)
    
    print(f"✅ Loaded data with {len(data.get('annotations', []))} annotations")
    
    # Set up category controller
    cat_controller = CategoryController()
    cat_controller.initialize_categories(data)
    
    print(f"📊 Found {len(cat_controller.categories)} categories:")
    for cat_id, cat_info in cat_controller.categories.items():
        count = sum(1 for ann in data['annotations'] if ann.get('category_id') == cat_id)
        color = cat_controller.get_category_color(cat_id)
        print(f"   - {cat_info['name']} (ID: {cat_id}): {count} annotations, color: {color}")
    
    # Filter to specific categories
    print("\n🔍 Filtering to show only first 2 categories...")
    cat_ids = list(cat_controller.categories.keys())[:2]
    
    cat_controller.select_none()
    for cat_id in cat_ids:
        cat_controller.toggle_category(cat_id, True)
    
    selected = cat_controller.get_selected_categories()
    print(f"✅ Selected categories: {selected}")
    
    # Load filtered data in napari
    layers = coco_reader(SAMPLE_COCO_FILE)
    if layers:
        viewer = napari.Viewer()
        shapes_data, metadata, layer_type = layers[0]
        
        # Filter the loaded data by category
        filtered_data = []
        filtered_properties = []
        filtered_colors = []
        
        for i, prop in enumerate(metadata['properties']):
            if prop['category_id'] in selected:
                filtered_data.append(shapes_data[i])
                filtered_properties.append(prop)
                filtered_colors.append(metadata['face_color'][i])
        
        # Create filtered metadata
        filtered_metadata = metadata.copy()
        filtered_metadata['properties'] = filtered_properties
        filtered_metadata['face_color'] = filtered_colors
        filtered_metadata['edge_color'] = filtered_colors
        filtered_metadata['shape_type'] = ['polygon'] * len(filtered_data)
        filtered_metadata['name'] = f'Filtered COCO ({len(filtered_data)} shapes)'
        
        # Add to viewer
        layer = viewer.add_shapes(filtered_data, **filtered_metadata)
        print(f"🖼️  Added filtered layer with {len(filtered_data)} shapes")
        
        napari.run()


def main():
    """Main function to run examples."""
    print("napari-cocoutils Usage Examples")
    print("=" * 50)
    
    examples = [
        ("1", "Direct reader usage", example_1_direct_reader),
        ("2", "Interactive widget usage", example_2_widget_usage), 
        ("3", "Programmatic filtering", example_3_programmatic_filtering)
    ]
    
    print("\nAvailable examples:")
    for num, desc, _ in examples:
        print(f"  {num}. {desc}")
    
    choice = input("\nSelect example (1-3) or 'all' to run all: ").strip()
    
    if choice.lower() == 'all':
        for num, desc, func in examples:
            print(f"\n{'='*60}")
            print(f"Running Example {num}: {desc}")
            print('='*60)
            try:
                func()
            except KeyboardInterrupt:
                print("\n⏹️  Example interrupted by user")
            except Exception as e:
                print(f"❌ Example failed: {e}")
            
            input("\nPress Enter to continue to next example...")
    
    elif choice in ['1', '2', '3']:
        example_func = examples[int(choice) - 1][2]
        try:
            example_func()
        except KeyboardInterrupt:
            print("\n⏹️  Example interrupted by user")
        except Exception as e:
            print(f"❌ Example failed: {e}")
    
    else:
        print("❌ Invalid choice. Please select 1, 2, 3, or 'all'")


if __name__ == "__main__":
    main()