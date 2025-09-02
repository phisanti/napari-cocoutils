"""
Tests for COCO controller classes.

This module tests the individual controller classes that handle
different aspects of COCO data management and visualization.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from napari_cocoutils._controllers import (
    CocoFileManager, CategoryController, NavigationController,
    VisualizationManager, DisplayController
)
from napari_cocoutils._utils import CocoError


@pytest.fixture
def sample_coco_data():
    """Sample COCO data for testing."""
    return {
        'images': [
            {'id': 1, 'file_name': 'image1.jpg', 'width': 640, 'height': 480},
            {'id': 2, 'file_name': 'image2.jpg', 'width': 800, 'height': 600}
        ],
        'categories': [
            {'id': 1, 'name': 'person'},
            {'id': 2, 'name': 'car'}
        ],
        'annotations': [
            {
                'id': 1, 'image_id': 1, 'category_id': 1,
                'segmentation': [[10, 10, 50, 10, 50, 50, 10, 50]],
                'area': 1600, 'bbox': [10, 10, 40, 40]
            },
            {
                'id': 2, 'image_id': 1, 'category_id': 2,
                'segmentation': [[100, 100, 150, 100, 150, 150, 100, 150]],
                'area': 2500, 'bbox': [100, 100, 50, 50]
            },
            {
                'id': 3, 'image_id': 2, 'category_id': 1,
                'segmentation': [[20, 20, 60, 20, 60, 60, 20, 60]],
                'area': 1600, 'bbox': [20, 20, 40, 40]
            }
        ]
    }


@pytest.fixture
def temp_coco_file(sample_coco_data):
    """Create temporary COCO file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_coco_data, f)
        return f.name


class TestCocoFileManager:
    """Test cases for CocoFileManager."""
    
    def test_initialization(self):
        """Test file manager initialization."""
        manager = CocoFileManager()
        assert manager.coco_data is None
        assert manager.file_path is None
        assert not manager.is_loaded()
    
    def test_successful_file_loading(self, temp_coco_file, sample_coco_data):
        """Test successful COCO file loading."""
        manager = CocoFileManager()
        data = manager.load_file(temp_coco_file)
        
        assert data == sample_coco_data
        assert manager.is_loaded()
        assert manager.file_path.name == Path(temp_coco_file).name
        
        # Test file info
        info = manager.get_file_info()
        assert info['num_annotations'] == 3
        assert info['num_images'] == 2
        assert info['num_categories'] == 2
        assert info['file_name'] == Path(temp_coco_file).name
    
    def test_invalid_file_loading(self):
        """Test loading of invalid files."""
        manager = CocoFileManager()
        
        with pytest.raises(CocoError):
            manager.load_file('nonexistent_file.json')
        
        assert not manager.is_loaded()
    
    def test_file_info_when_no_data_loaded(self):
        """Test get_file_info when no data is loaded."""
        manager = CocoFileManager()
        info = manager.get_file_info()
        assert info == {}


class TestCategoryController:
    """Test cases for CategoryController."""
    
    def test_initialization(self):
        """Test category controller initialization."""
        controller = CategoryController()
        assert len(controller.category_states) == 0
        assert len(controller.category_colors) == 0
        assert len(controller.categories) == 0
    
    def test_category_initialization(self, sample_coco_data):
        """Test category initialization from COCO data."""
        controller = CategoryController()
        controller.initialize_categories(sample_coco_data)
        
        assert len(controller.categories) == 2
        assert 1 in controller.categories
        assert 2 in controller.categories
        assert controller.categories[1]['name'] == 'person'
        assert controller.categories[2]['name'] == 'car'
        
        # All categories should start as visible
        assert all(controller.category_states.values())
        
        # Colors should be generated
        assert len(controller.category_colors) == 2
        assert 1 in controller.category_colors
        assert 2 in controller.category_colors
    
    def test_category_toggle(self, sample_coco_data):
        """Test category visibility toggle."""
        controller = CategoryController()
        controller.initialize_categories(sample_coco_data)
        
        # Toggle category 1 off
        controller.toggle_category(1, False)
        assert controller.category_states[1] is False
        assert controller.category_states[2] is True
        
        # Toggle category 1 back on
        controller.toggle_category(1, True)
        assert controller.category_states[1] is True
    
    def test_get_selected_categories(self, sample_coco_data):
        """Test getting selected categories."""
        controller = CategoryController()
        controller.initialize_categories(sample_coco_data)
        
        # Initially all selected
        selected = controller.get_selected_categories()
        assert len(selected) == 2
        assert 1 in selected
        assert 2 in selected
        
        # Toggle one off
        controller.toggle_category(1, False)
        selected = controller.get_selected_categories()
        assert len(selected) == 1
        assert 1 not in selected
        assert 2 in selected
    
    def test_select_all_none(self, sample_coco_data):
        """Test select all and select none functionality."""
        controller = CategoryController()
        controller.initialize_categories(sample_coco_data)
        
        # Select none
        controller.select_none()
        selected = controller.get_selected_categories()
        assert len(selected) == 0
        
        # Select all
        controller.select_all()
        selected = controller.get_selected_categories()
        assert len(selected) == 2
        assert 1 in selected
        assert 2 in selected
    
    def test_get_category_color(self, sample_coco_data):
        """Test getting category colors."""
        controller = CategoryController()
        controller.initialize_categories(sample_coco_data)
        
        color1 = controller.get_category_color(1)
        color2 = controller.get_category_color(2)
        
        assert isinstance(color1, tuple)
        assert len(color1) == 4  # RGBA
        assert isinstance(color2, tuple)
        assert len(color2) == 4  # RGBA
        
        # Colors should be different
        assert color1 != color2
        
        # Unknown category should return white
        unknown_color = controller.get_category_color(999)
        assert unknown_color == (1.0, 1.0, 1.0, 1.0)


class TestNavigationController:
    """Test cases for NavigationController."""
    
    def test_initialization(self):
        """Test navigation controller initialization."""
        controller = NavigationController()
        assert controller.current_image_idx == 0
        assert len(controller.images) == 0
    
    def test_image_initialization(self, sample_coco_data):
        """Test image initialization from COCO data."""
        controller = NavigationController()
        controller.initialize_images(sample_coco_data)
        
        assert len(controller.images) == 2
        assert controller.current_image_idx == 0
        assert controller.images[0]['file_name'] == 'image1.jpg'
        assert controller.images[1]['file_name'] == 'image2.jpg'
    
    def test_get_current_image(self, sample_coco_data):
        """Test getting current image info."""
        controller = NavigationController()
        controller.initialize_images(sample_coco_data)
        
        current = controller.get_current_image()
        assert current is not None
        assert current['file_name'] == 'image1.jpg'
        assert current['id'] == 1
        
        current_id = controller.get_current_image_id()
        assert current_id == 1
    
    def test_navigation_methods(self, sample_coco_data):
        """Test navigation functionality."""
        controller = NavigationController()
        controller.initialize_images(sample_coco_data)
        
        # Initially at first image
        assert controller.current_image_idx == 0
        assert not controller.can_go_previous()
        assert controller.can_go_next()
        
        # Navigate to next
        result = controller.go_next()
        assert result is True
        assert controller.current_image_idx == 1
        assert controller.can_go_previous()
        assert not controller.can_go_next()
        
        # Navigate back
        result = controller.go_previous()
        assert result is True
        assert controller.current_image_idx == 0
        
        # Try to go beyond bounds
        result = controller.go_previous()
        assert result is False
        assert controller.current_image_idx == 0
    
    def test_navigate_to_image(self, sample_coco_data):
        """Test direct navigation to specific image index."""
        controller = NavigationController()
        controller.initialize_images(sample_coco_data)
        
        # Navigate to valid index
        result = controller.navigate_to_image(1)
        assert result is True
        assert controller.current_image_idx == 1
        
        # Navigate to invalid index
        result = controller.navigate_to_image(5)
        assert result is False
        assert controller.current_image_idx == 1  # Should remain unchanged
        
        result = controller.navigate_to_image(-1)
        assert result is False
        assert controller.current_image_idx == 1
    
    def test_has_multiple_images(self, sample_coco_data):
        """Test multiple images detection."""
        controller = NavigationController()
        
        # No images loaded
        assert not controller.has_multiple_images()
        
        # Load multi-image data
        controller.initialize_images(sample_coco_data)
        assert controller.has_multiple_images()
        
        # Single image data
        single_image_data = {
            'images': [{'id': 1, 'file_name': 'single.jpg', 'width': 100, 'height': 100}],
            'categories': [],
            'annotations': []
        }
        controller.initialize_images(single_image_data)
        assert not controller.has_multiple_images()


class TestVisualizationManager:
    """Test cases for VisualizationManager."""
    
    def test_initialization(self):
        """Test visualization manager initialization."""
        mock_viewer = Mock()
        manager = VisualizationManager(mock_viewer)
        
        assert manager.viewer is mock_viewer
        assert manager.current_shapes_layer is None
        assert manager.visualizer is None
        assert manager.n_filter_value is None
    
    def test_visualizer_initialization(self, sample_coco_data):
        """Test visualizer initialization."""
        mock_viewer = Mock()
        manager = VisualizationManager(mock_viewer)
        
        manager.initialize_visualizer(sample_coco_data)
        assert manager.visualizer is not None
    
    def test_n_filter_setting(self):
        """Test N-filter value setting."""
        mock_viewer = Mock()
        manager = VisualizationManager(mock_viewer)
        
        manager.set_n_filter(100)
        assert manager.n_filter_value == 100
    
    def test_cleanup(self):
        """Test visualization cleanup."""
        mock_viewer = Mock()
        mock_layer = Mock()
        mock_layers = Mock()
        mock_layers.__contains__ = Mock(return_value=True)  # Mock the 'in' operator
        mock_viewer.layers = mock_layers
        
        manager = VisualizationManager(mock_viewer)
        manager.current_shapes_layer = mock_layer
        
        manager.cleanup()
        assert manager.current_shapes_layer is None
        mock_layers.remove.assert_called_once_with(mock_layer)


class TestDisplayController:
    """Test cases for DisplayController."""
    
    def test_initialization(self):
        """Test display controller initialization."""
        controller = DisplayController()
        assert controller.n_filter_value == 1000
        assert controller.visualization_mode == 'overlay'
    
    def test_n_filter_setting(self):
        """Test N-filter value setting."""
        controller = DisplayController()
        
        controller.set_n_filter(500)
        assert controller.n_filter_value == 500
        
        # Test minimum value enforcement
        controller.set_n_filter(-10)
        assert controller.n_filter_value == 1  # Should be at least 1
    
    def test_visualization_mode_setting(self):
        """Test visualization mode setting."""
        controller = DisplayController()
        
        controller.set_visualization_mode('masked')
        assert controller.visualization_mode == 'masked'
        
        controller.set_visualization_mode('overlay')
        assert controller.visualization_mode == 'overlay'
        
        # Invalid mode should be ignored
        controller.set_visualization_mode('invalid')
        assert controller.visualization_mode == 'overlay'  # Should remain unchanged
    
    def test_annotation_count_info(self, sample_coco_data):
        """Test annotation count information."""
        controller = DisplayController()
        
        # Test with no data
        info = controller.get_annotation_count_info({}, 1, [1])
        assert info == {'visible': 0, 'total': 0}
        
        # Test with sample data
        info = controller.get_annotation_count_info(sample_coco_data, 1, [1, 2])
        assert info['visible'] == 2  # Image 1 has 2 annotations
        assert info['total'] == 3    # Total across all images
        
        # Test with category filter
        info = controller.get_annotation_count_info(sample_coco_data, 1, [1])
        assert info['visible'] == 1  # Only category 1 annotations
        assert info['total'] == 3    # Total unchanged
        
        # Test with different image
        info = controller.get_annotation_count_info(sample_coco_data, 2, [1, 2])
        assert info['visible'] == 1  # Image 2 has 1 annotation
        assert info['total'] == 3    # Total unchanged


class TestControllersIntegration:
    """Integration tests for controller interactions."""
    
    def test_full_workflow(self, temp_coco_file, sample_coco_data):
        """Test complete workflow with all controllers."""
        # Initialize all controllers
        file_manager = CocoFileManager()
        category_controller = CategoryController()
        nav_controller = NavigationController()
        display_controller = DisplayController()
        
        # Load file
        data = file_manager.load_file(temp_coco_file)
        
        # Initialize other controllers
        category_controller.initialize_categories(data)
        nav_controller.initialize_images(data)
        
        # Test workflow
        assert file_manager.is_loaded()
        assert len(category_controller.categories) == 2
        assert len(nav_controller.images) == 2
        
        # Navigate and filter
        nav_controller.go_next()
        category_controller.toggle_category(2, False)
        
        # Check final state
        current_image_id = nav_controller.get_current_image_id()
        selected_categories = category_controller.get_selected_categories()
        count_info = display_controller.get_annotation_count_info(
            data, current_image_id, selected_categories
        )
        
        assert current_image_id == 2
        assert len(selected_categories) == 1
        assert 1 in selected_categories
        assert count_info['visible'] == 1  # Image 2, category 1 only