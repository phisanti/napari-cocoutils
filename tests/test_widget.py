"""
Tests for COCO widget GUI functionality.

This module tests the napari widget implementation,
user interactions, and integration with napari viewer.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication

import napari
from napari_cocoutils._widget import CocoWidget
from napari_cocoutils._utils import CocoError


# Test data fixtures
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


@pytest.fixture
def mock_viewer():
    """Fixture providing mock napari viewer."""
    viewer = Mock(spec=napari.Viewer)
    viewer.layers = Mock()
    viewer.add_shapes = Mock(return_value=Mock())
    return viewer


@pytest.fixture
def widget(mock_viewer):
    """Fixture providing CocoWidget instance."""
    return CocoWidget(mock_viewer)


class TestCocoWidget:
    """Test cases for COCO widget GUI functionality."""
    
    def test_widget_initialization(self, widget, mock_viewer):
        """Test widget initializes correctly."""
        assert widget.viewer is mock_viewer
        assert widget.file_manager is not None
        assert widget.category_controller is not None
        assert widget.navigation_controller is not None
        assert widget.visualization_manager is not None
        assert widget.display_controller is not None
        assert isinstance(widget.category_checkboxes, dict)
        assert len(widget.category_checkboxes) == 0  # Initially empty
    
    @patch('napari_cocoutils._widget.QFileDialog')
    def test_file_selection_success(self, mock_dialog, widget, temp_coco_file):
        """Test successful file selection and loading."""
        # Mock file dialog to return test file
        mock_dialog.getOpenFileName.return_value = (temp_coco_file, "*.json")
        
        # Trigger file selection
        widget.on_file_selected()
        
        # Verify file was loaded
        assert widget.file_manager.is_loaded()
        assert widget.file_manager.file_path.name == Path(temp_coco_file).name
        
        # Verify UI updates
        assert "✓ Loaded:" in widget.status_label.text()
        assert widget.file_path_label.text() == Path(temp_coco_file).name
        
        # Verify controls are enabled
        assert widget.select_all_btn.isEnabled()
        assert widget.select_none_btn.isEnabled()
        assert widget.n_filter_spinbox.isEnabled()
    
    @patch('napari_cocoutils._widget.QFileDialog')
    def test_file_selection_cancelled(self, mock_dialog, widget):
        """Test file selection dialog cancellation."""
        # Mock cancelled file dialog
        mock_dialog.getOpenFileName.return_value = ("", "")
        
        # Trigger file selection
        widget.on_file_selected()
        
        # Verify no file was loaded
        assert not widget.file_manager.is_loaded()
        assert widget.status_label.text() == "Ready to load COCO file"
    
    @patch('napari_cocoutils._widget.QFileDialog')
    def test_invalid_file_handling(self, mock_dialog, widget):
        """Test handling of invalid COCO files."""
        # Create invalid JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            invalid_file = f.name
        
        # Mock file dialog to return invalid file
        mock_dialog.getOpenFileName.return_value = (invalid_file, "*.json")
        
        # Trigger file selection
        widget.on_file_selected()
        
        # Verify error handling
        assert not widget.file_manager.is_loaded()
        assert "✗" in widget.status_label.text()
        
        # Clean up
        Path(invalid_file).unlink()
    
    def test_category_controls_creation(self, widget, temp_coco_file):
        """Test category checkbox creation from COCO data."""
        # Load test data
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        
        # Update category controls
        widget._update_category_controls()
        
        # Verify checkboxes were created
        assert len(widget.category_checkboxes) == 2  # person, car
        
        # Check checkbox properties
        for cat_id, checkbox in widget.category_checkboxes.items():
            assert checkbox.isChecked()  # Initially all selected
            assert checkbox.text().startswith(widget.category_controller.categories[cat_id]['name'])
    
    def test_category_toggle_functionality(self, widget, temp_coco_file):
        """Test category visibility toggle."""
        # Load and setup widget
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Test category toggle
        widget.on_category_toggled(1, False)  # Disable category 1
        
        # Verify state update
        assert widget.category_controller.category_states[1] is False
        assert widget.category_controller.category_states[2] is True
        
        # Verify only enabled categories are selected
        selected = widget.category_controller.get_selected_categories()
        assert 1 not in selected
        assert 2 in selected
    
    def test_image_navigation_setup(self, widget, temp_coco_file):
        """Test image navigation setup with multi-image dataset."""
        # Load test data
        widget.file_manager.load_file(temp_coco_file)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        
        # Update navigation UI
        widget._update_image_navigation()
        
        # Verify combo box populated
        assert widget.image_combo.count() == 2
        assert "image1.jpg" in widget.image_combo.itemText(0)
        assert "image2.jpg" in widget.image_combo.itemText(1)
        
        # Verify navigation state
        assert widget.navigation_controller.has_multiple_images()
        assert widget.navigation_controller.current_image_idx == 0
    
    def test_image_navigation_controls(self, widget, temp_coco_file):
        """Test image navigation functionality."""
        # Setup widget with test data
        widget.file_manager.load_file(temp_coco_file)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Test navigation
        assert widget.navigation_controller.current_image_idx == 0
        assert widget.navigation_controller.can_go_next()
        assert not widget.navigation_controller.can_go_previous()
        
        # Navigate to next image
        widget._on_next_image()
        assert widget.navigation_controller.current_image_idx == 1
        assert not widget.navigation_controller.can_go_next()
        assert widget.navigation_controller.can_go_previous()
        
        # Navigate back
        widget._on_prev_image()
        assert widget.navigation_controller.current_image_idx == 0
    
    def test_annotation_count_display(self, widget, temp_coco_file):
        """Test annotation count display functionality."""
        # Setup widget
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        
        # Update annotation count
        widget._update_annotation_count()
        
        # Verify count display (image 1 has 2 annotations, total is 3)
        count_text = widget.annotation_count_label.text()
        assert "/ 2 visible (3 total)" in count_text
    
    def test_n_filter_functionality(self, widget, temp_coco_file):
        """Test N-filter for annotation sampling."""
        # Setup widget
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Set N-filter value
        widget._on_n_filter_changed(1)
        
        # Verify display controller updated
        assert widget.display_controller.n_filter_value == 1
    
    def test_select_all_categories(self, widget, temp_coco_file):
        """Test select all categories functionality."""
        # Setup widget
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget._update_category_controls()
        
        # Deselect a category first
        widget.category_controller.toggle_category(1, False)
        
        # Select all
        widget._select_all_categories()
        
        # Verify all categories selected
        selected = widget.category_controller.get_selected_categories()
        assert len(selected) == 2
        assert 1 in selected
        assert 2 in selected
    
    def test_select_none_categories(self, widget, temp_coco_file):
        """Test select none categories functionality."""
        # Setup widget
        widget.file_manager.load_file(temp_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget._update_category_controls()
        
        # Deselect all
        widget._select_none_categories()
        
        # Verify no categories selected
        selected = widget.category_controller.get_selected_categories()
        assert len(selected) == 0
    
    def test_visualization_mode_change(self, widget):
        """Test visualization mode switching."""
        # Test overlay mode (default)
        assert widget.display_controller.visualization_mode == 'overlay'
        
        # Switch to masked mode
        widget.masked_radio.setChecked(True)
        widget._on_viz_mode_changed()
        
        # Verify mode change
        assert widget.display_controller.visualization_mode == 'masked'
    
    def test_widget_cleanup(self, widget, temp_coco_file):
        """Test proper cleanup when resetting controllers."""
        # Load data
        widget.file_manager.load_file(temp_coco_file)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        
        # Reset controllers
        widget._reset_controllers()
        
        # Verify cleanup
        assert not widget.file_manager.is_loaded()
        assert len(widget.category_controller.categories) == 0
        assert len(widget.navigation_controller.images) == 0


class TestCocoWidgetIntegration:
    """Integration tests for COCO widget with napari."""
    
    def test_widget_with_real_viewer(self, sample_coco_data):
        """Test widget integration with actual napari viewer."""
        pytest.importorskip("napari")
        
        # Create real napari viewer (headless)
        viewer = napari.Viewer(show=False)
        
        try:
            # Create widget
            widget = CocoWidget(viewer)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(sample_coco_data, f)
                temp_file = f.name
            
            # Load data
            widget.file_manager.load_file(temp_file)
            widget.category_controller.initialize_categories(widget.file_manager.coco_data)
            widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
            widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
            
            # Test visualization
            widget._refresh_visualization()
            
            # Verify layer was created (should have shapes layer)
            assert len(viewer.layers) > 0
            
            # Clean up
            Path(temp_file).unlink()
            
        finally:
            viewer.close()