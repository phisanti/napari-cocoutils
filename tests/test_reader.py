"""
Tests for COCO file reader functionality.

This module tests the napari reader hook implementation,
COCO file detection, validation, and conversion to napari layers.
"""

import pytest
import json
import tempfile
from pathlib import Path
from napari_cocoutils._reader import coco_reader, _is_coco_file, _convert_coco_to_napari


@pytest.fixture
def sample_coco_data():
    """Fixture providing sample COCO data for testing."""
    return {
        'images': [
            {'id': 1, 'file_name': 'test.jpg', 'width': 640, 'height': 480}
        ],
        'categories': [
            {'id': 1, 'name': 'person'},
            {'id': 2, 'name': 'car'}
        ],
        'annotations': [
            {
                'id': 1,
                'image_id': 1,
                'category_id': 1,
                'segmentation': [[10, 10, 50, 10, 50, 50, 10, 50]],
                'area': 1600,
                'bbox': [10, 10, 40, 40]
            },
            {
                'id': 2,
                'image_id': 1,
                'category_id': 2,
                'bbox': [100, 100, 50, 30],
                'area': 1500
            }
        ]
    }


@pytest.fixture
def temp_coco_file(sample_coco_data):
    """Fixture providing temporary COCO JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_coco_data, f)
        return f.name


@pytest.fixture
def invalid_json_file():
    """Fixture providing invalid JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("invalid json content {")
        return f.name


@pytest.fixture
def non_coco_json_file():
    """Fixture providing valid JSON but non-COCO structure."""
    non_coco_data = {
        'some_other_field': 'value',
        'data': [1, 2, 3, 4]
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(non_coco_data, f)
        return f.name


class TestCocoReader:
    """Test cases for COCO file reader functionality."""
    
    def test_coco_reader_with_valid_file(self, temp_coco_file):
        """Test reader with valid COCO JSON file."""
        result = coco_reader(temp_coco_file)
        
        # Should return list of LayerDataTuple
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check layer data tuple format
        layer_data = result[0]
        assert len(layer_data) == 3  # (data, metadata, layer_type)
        
        data, metadata, layer_type = layer_data
        assert layer_type == 'shapes'
        assert isinstance(metadata, dict)
        
        # Clean up
        Path(temp_coco_file).unlink()
    
    def test_coco_reader_with_invalid_json(self, invalid_json_file):
        """Test reader with invalid JSON file."""
        result = coco_reader(invalid_json_file)
        
        # Should return None for invalid JSON
        assert result is None
        
        # Clean up
        Path(invalid_json_file).unlink()
    
    def test_coco_reader_with_non_coco_file(self, non_coco_json_file):
        """Test reader with valid JSON but non-COCO structure."""
        result = coco_reader(non_coco_json_file)
        
        # Should return None for non-COCO JSON
        assert result is None
        
        # Clean up
        Path(non_coco_json_file).unlink()
    
    def test_coco_reader_with_non_json_file(self):
        """Test reader with non-JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is not a JSON file")
            txt_file = f.name
        
        result = coco_reader(txt_file)
        
        # Should return None for non-JSON files
        assert result is None
        
        # Clean up
        Path(txt_file).unlink()
    
    def test_coco_reader_with_nonexistent_file(self):
        """Test reader with nonexistent file."""
        result = coco_reader('nonexistent_file.json')
        
        # Should return None for missing files
        assert result is None
    
    def test_is_coco_file_validation(self, sample_coco_data):
        """Test COCO file format validation."""
        from napari_cocoutils._utils import validate_coco_structure
        
        # Test with valid COCO structure
        assert validate_coco_structure(sample_coco_data) is True
        
        # Test with missing required fields
        invalid_data = {'images': [], 'categories': []}  # Missing annotations
        assert validate_coco_structure(invalid_data) is False
        
        # Test with wrong field types
        invalid_data = {'images': 'not_a_list', 'categories': [], 'annotations': []}
        assert validate_coco_structure(invalid_data) is False
        
        # Test with empty dictionary
        assert validate_coco_structure({}) is False
        
        # Test with None
        assert validate_coco_structure(None) is False
    
    def test_convert_coco_to_napari_layers(self, sample_coco_data):
        """Test conversion from COCO data to napari layers."""
        result = _convert_coco_to_napari(sample_coco_data, "test.json")
        
        # Should return list of layer data tuples
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check first layer (shapes layer)
        data, metadata, layer_type = result[0]
        
        assert layer_type == 'shapes'
        assert isinstance(metadata, dict)
        assert 'properties' in metadata
        assert 'name' in metadata
        
        # Should have shapes data (polygons and rectangles)
        assert isinstance(data, list)
        assert len(data) > 0  # Should have at least one shape
    
    def test_convert_coco_polygon_annotations(self):
        """Test conversion of COCO polygon annotations."""
        coco_data = {
            'images': [
                {'id': 1, 'file_name': 'test.jpg', 'width': 100, 'height': 100}
            ],
            'categories': [
                {'id': 1, 'name': 'test_category'}
            ],
            'annotations': [
                {
                    'id': 1,
                    'image_id': 1,
                    'category_id': 1,
                    'segmentation': [[10, 10, 30, 10, 30, 30, 10, 30]],
                    'area': 400
                }
            ]
        }
        
        result = _convert_coco_to_napari(coco_data, "test.json")
        
        assert len(result) == 1
        data, metadata, layer_type = result[0]
        
        assert layer_type == 'shapes'
        assert len(data) == 1  # One polygon
        
        # Check polygon shape
        polygon = data[0]
        assert polygon.shape == (4, 2)  # 4 points, 2 coordinates each
    
    def test_convert_coco_bbox_annotations(self):
        """Test conversion of COCO bounding box annotations."""
        coco_data = {
            'images': [
                {'id': 1, 'file_name': 'test.jpg', 'width': 100, 'height': 100}
            ],
            'categories': [
                {'id': 1, 'name': 'test_category'}
            ],
            'annotations': [
                {
                    'id': 1,
                    'image_id': 1,
                    'category_id': 1,
                    'bbox': [10, 10, 20, 20],
                    'area': 400
                }
            ]
        }
        
        result = _convert_coco_to_napari(coco_data, "test.json")
        
        assert len(result) == 1
        data, metadata, layer_type = result[0]
        
        assert layer_type == 'shapes'
        assert len(data) == 1  # One rectangle
        
        # Check rectangle shape
        rectangle = data[0]
        assert rectangle.shape == (4, 2)  # 4 corners, 2 coordinates each
    
    def test_convert_empty_annotations(self):
        """Test conversion with no annotations."""
        coco_data = {
            'images': [
                {'id': 1, 'file_name': 'test.jpg', 'width': 100, 'height': 100}
            ],
            'categories': [
                {'id': 1, 'name': 'test_category'}
            ],
            'annotations': []
        }
        
        result = _convert_coco_to_napari(coco_data, "test.json")
        
        # Should return empty list when no annotations
        assert len(result) == 0
    
    def test_convert_mixed_annotations(self):
        """Test conversion with both polygon and bbox annotations."""
        coco_data = {
            'images': [
                {'id': 1, 'file_name': 'test.jpg', 'width': 100, 'height': 100}
            ],
            'categories': [
                {'id': 1, 'name': 'polygon_cat'},
                {'id': 2, 'name': 'bbox_cat'}
            ],
            'annotations': [
                {
                    'id': 1,
                    'image_id': 1,
                    'category_id': 1,
                    'segmentation': [[10, 10, 30, 10, 30, 30, 10, 30]],
                    'area': 400
                },
                {
                    'id': 2,
                    'image_id': 1,
                    'category_id': 2,
                    'bbox': [50, 50, 20, 20],
                    'area': 400
                }
            ]
        }
        
        result = _convert_coco_to_napari(coco_data, "test.json")
        
        assert len(result) == 1
        data, metadata, layer_type = result[0]
        
        assert layer_type == 'shapes'
        assert len(data) == 2  # One polygon + one rectangle
        
        # Check metadata
        assert len(metadata['properties']) == 2
        assert len(metadata['shape_type']) == 2
    
    def test_category_colors_and_properties(self, sample_coco_data):
        """Test that categories get proper colors and properties."""
        result = _convert_coco_to_napari(sample_coco_data, "test.json")
        
        data, metadata, layer_type = result[0]
        
        # Check properties
        properties = metadata['properties']
        assert len(properties) >= 1
        
        for prop in properties:
            assert 'category_id' in prop
            assert 'category_name' in prop
            assert 'annotation_id' in prop
        
        # Check colors
        assert 'face_color' in metadata
        assert 'edge_color' in metadata
        
        face_colors = metadata['face_color']
        edge_colors = metadata['edge_color']
        
        assert len(face_colors) == len(data)
        assert len(edge_colors) == len(data)
        
        # Each color should be RGBA tuple
        for color in face_colors:
            assert isinstance(color, tuple)
            assert len(color) == 4  # RGBA
    
    def test_invalid_annotation_handling(self):
        """Test handling of invalid/malformed annotations."""
        coco_data = {
            'images': [
                {'id': 1, 'file_name': 'test.jpg', 'width': 100, 'height': 100}
            ],
            'categories': [
                {'id': 1, 'name': 'test_category'}
            ],
            'annotations': [
                {
                    'id': 1,
                    'image_id': 1,
                    'category_id': 1,
                    'segmentation': [[10, 10]],  # Invalid - too few points
                    'area': 0
                },
                {
                    'id': 2,
                    'image_id': 1,
                    'category_id': 1,
                    'bbox': [10, 10, 20],  # Invalid - incomplete bbox
                    'area': 0
                },
                {
                    'id': 3,
                    'image_id': 1,
                    'category_id': 1,
                    'segmentation': [[10, 10, 30, 10, 30, 30, 10, 30]],  # Valid
                    'area': 400
                }
            ]
        }
        
        result = _convert_coco_to_napari(coco_data, "test.json")
        
        assert len(result) == 1
        data, metadata, layer_type = result[0]
        
        # Should only have one valid shape (invalid ones filtered out)
        assert len(data) == 1
        assert len(metadata['properties']) == 1