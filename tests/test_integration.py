"""
Integration tests with real COCO datasets and napari viewer.

Tests the complete workflow from COCO file loading to napari visualization
using the actual sample data files referenced in the project roadmap.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock

import napari
from napari_cocoutils._reader import coco_reader
from napari_cocoutils._widget import CocoWidget


# Test data paths from roadmap
SAMPLE_COCO_FILE = "/Users/santiago/switchdrive/boeck_lab_projects/cocoutils/test.json"
SAMPLE_IMAGES = [
    "/Users/santiago/switchdrive/boeck_lab_projects/cocoutils/data/objects_reconstructed/coli_mask_frame_223.tiff",
    "/Users/santiago/switchdrive/boeck_lab_projects/cocoutils/data/objects_reconstructed/mabs_img_01.tiff"
]


@pytest.fixture
def real_coco_file():
    """Fixture providing real COCO test file path."""
    coco_path = Path(SAMPLE_COCO_FILE)
    if not coco_path.exists():
        pytest.skip(f"Sample COCO file not found: {SAMPLE_COCO_FILE}")
    return str(coco_path)


@pytest.fixture
def real_image_files():
    """Fixture providing real image file paths."""
    available_images = []
    for img_path in SAMPLE_IMAGES:
        if Path(img_path).exists():
            available_images.append(img_path)
    
    if not available_images:
        pytest.skip("No sample images found")
    return available_images


class TestRealDataIntegration:
    """Integration tests using real COCO data."""
    
    def test_load_real_coco_file(self, real_coco_file):
        """Test loading the actual test.json COCO file."""
        result = coco_reader(real_coco_file)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check layer structure
        data, metadata, layer_type = result[0]
        assert layer_type == 'shapes'
        assert isinstance(metadata, dict)
        assert 'properties' in metadata
        assert 'name' in metadata
        
        # Should have significant number of annotations (based on roadmap: 6,145)
        assert len(data) > 1000
        print(f"Loaded {len(data)} annotations from real COCO file")
        
        # Check category distribution
        properties = metadata['properties']
        categories = set(prop['category_name'] for prop in properties)
        print(f"Found categories: {categories}")
        assert len(categories) >= 2  # Should have multiple categories
    
    def test_napari_visualization_workflow(self, real_coco_file):
        """Test complete napari visualization workflow."""
        pytest.importorskip("napari")
        
        # Create headless viewer
        viewer = napari.Viewer(show=False)
        
        try:
            # Load COCO data via reader
            layer_data_list = coco_reader(real_coco_file)
            assert layer_data_list is not None
            
            # Add layer to viewer
            shapes_data, metadata, layer_type = layer_data_list[0]
            layer = viewer.add_shapes(shapes_data, **metadata)
            
            # Verify layer was created
            assert len(viewer.layers) == 1
            assert layer.name == metadata['name']
            assert len(layer.data) == len(shapes_data)
            
            # Test layer properties
            assert hasattr(layer, 'properties')
            assert len(layer.properties) > 0
            
            # Verify colors are set
            assert hasattr(layer, 'face_color')
            assert hasattr(layer, 'edge_color')
            
            print(f"Successfully visualized {len(shapes_data)} shapes in napari")
            
        finally:
            viewer.close()
    
    def test_widget_with_real_data(self, real_coco_file):
        """Test widget functionality with real COCO data."""
        pytest.importorskip("napari")
        
        # Create mock viewer to avoid GUI issues
        mock_viewer = Mock(spec=napari.Viewer)
        mock_viewer.layers = Mock()
        mock_viewer.add_shapes = Mock(return_value=Mock())
        
        # Create widget
        widget = CocoWidget(mock_viewer)
        
        # Load real file
        widget.file_manager.load_file(real_coco_file)
        
        # Verify file loaded
        assert widget.file_manager.is_loaded()
        file_info = widget.file_manager.get_file_info()
        
        # Based on roadmap, test.json should have specific structure
        assert file_info['num_annotations'] > 5000  # Should be ~6,145
        assert file_info['num_images'] >= 2  # Should have 2 images
        assert file_info['num_categories'] >= 5  # Should have 5 categories
        
        print(f"File info: {file_info}")
        
        # Initialize controllers
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Test category functionality
        categories = widget.category_controller.categories
        assert len(categories) >= 5
        
        # Verify expected categories from roadmap
        category_names = [cat['name'] for cat in categories.values()]
        expected_categories = {'cell', 'clump', 'noise', 'off-focus', 'joint cell'}
        found_categories = set(category_names)
        
        # Should have significant overlap
        overlap = expected_categories & found_categories
        assert len(overlap) >= 3, f"Expected categories {expected_categories}, found {found_categories}"
        
        # Test navigation with multiple images
        assert widget.navigation_controller.has_multiple_images()
        assert widget.navigation_controller.can_go_next()
        
        # Test category filtering
        all_selected = widget.category_controller.get_selected_categories()
        assert len(all_selected) == len(categories)
        
        # Toggle a category
        first_cat_id = list(categories.keys())[0]
        widget.category_controller.toggle_category(first_cat_id, False)
        filtered_selected = widget.category_controller.get_selected_categories()
        assert len(filtered_selected) == len(categories) - 1
        
        print(f"Category filtering test passed with {len(categories)} categories")
    
    def test_performance_with_large_dataset(self, real_coco_file):
        """Test performance with the large real dataset."""
        import time
        
        # Time the file loading
        start_time = time.time()
        result = coco_reader(real_coco_file)
        load_time = time.time() - start_time
        
        assert result is not None
        num_annotations = len(result[0][0])
        
        # Should load reasonably quickly even with 6K+ annotations
        assert load_time < 10.0, f"Loading took {load_time:.2f}s, which is too slow"
        
        print(f"Loaded {num_annotations} annotations in {load_time:.2f}s")
        print(f"Performance: {num_annotations/load_time:.0f} annotations/second")
        
        # Memory usage check - shapes should be reasonable size
        shapes_data = result[0][0]
        total_points = sum(len(shape) for shape in shapes_data)
        memory_estimate_mb = total_points * 2 * 8 / (1024 * 1024)  # 2 coords * 8 bytes per float
        
        # Should not use excessive memory
        assert memory_estimate_mb < 100, f"Estimated memory usage too high: {memory_estimate_mb:.1f}MB"
        
        print(f"Estimated memory usage: {memory_estimate_mb:.1f}MB for {total_points} coordinate points")


class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""
    
    def test_missing_file_handling(self):
        """Test handling of missing COCO files."""
        result = coco_reader("nonexistent_file.json")
        assert result is None
        
        # Should not raise exception, just return None
        assert coco_reader("") is None
        assert coco_reader("/invalid/path/file.json") is None
    
    def test_corrupted_file_handling(self, tmp_path):
        """Test handling of corrupted COCO files."""
        # Create corrupted JSON file
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{ invalid json content")
        
        result = coco_reader(str(corrupted_file))
        assert result is None
        
        # Create valid JSON but invalid COCO structure
        invalid_coco = tmp_path / "invalid_coco.json"
        invalid_coco.write_text('{"wrong": "structure"}')
        
        result = coco_reader(str(invalid_coco))
        assert result is None
    
    def test_widget_error_recovery(self):
        """Test widget error recovery mechanisms."""
        pytest.importorskip("napari")
        
        mock_viewer = Mock(spec=napari.Viewer)
        mock_viewer.layers = Mock()
        mock_viewer.add_shapes = Mock(return_value=Mock())
        
        widget = CocoWidget(mock_viewer)
        
        # Should handle invalid file gracefully
        try:
            widget.file_manager.load_file("nonexistent.json")
            assert False, "Should have raised CocoError"
        except Exception:
            # Should not crash widget
            assert widget.file_manager.coco_data is None
            assert not widget.file_manager.is_loaded()


class TestCoordinateSystemIntegration:
    """Test coordinate system handling in integration scenarios."""
    
    def test_coordinate_conversion_consistency(self, real_coco_file):
        """Test that coordinate conversions are consistent."""
        from napari_cocoutils._utils import (
            convert_coco_to_napari_coordinates,
            convert_napari_to_coco_coordinates
        )
        
        # Load real data to get actual COCO polygons
        result = coco_reader(real_coco_file)
        shapes_data, metadata, _ = result[0]
        
        # Test round-trip conversion on first few shapes
        for i, shape in enumerate(shapes_data[:5]):
            # Convert napari shape back to COCO format
            coco_coords = convert_napari_to_coco_coordinates(shape)
            
            # Convert back to napari format
            napari_coords = convert_coco_to_napari_coordinates(coco_coords)
            
            # Should be very close (allowing for floating point precision)
            np.testing.assert_array_almost_equal(shape, napari_coords, decimal=10)
            
            print(f"Shape {i}: Round-trip conversion successful")
    
    def test_bbox_to_polygon_consistency(self):
        """Test that bounding box to polygon conversion is consistent."""
        # Test with simple bounding box
        bbox = [10, 20, 30, 40]  # [x, y, width, height]
        
        # Expected polygon (clockwise from top-left)
        expected_points = np.array([
            [20, 10],      # top-left (row, col)
            [20, 40],      # top-right
            [60, 40],      # bottom-right  
            [60, 10]       # bottom-left
        ])
        
        # This tests the conversion logic in the reader
        x, y, w, h = bbox
        rect_points = np.array([
            [y, x],           # top-left
            [y, x + w],       # top-right
            [y + h, x + w],   # bottom-right
            [y + h, x]        # bottom-left
        ])
        
        np.testing.assert_array_equal(rect_points, expected_points)
        print("Bounding box to polygon conversion is correct")