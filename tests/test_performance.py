"""
Performance tests for napari-cocoutils plugin.

Tests memory usage, loading times, and responsiveness with large datasets
to ensure the plugin can handle real-world COCO annotation files efficiently.
"""

import pytest
import time
import psutil
import os
from pathlib import Path
from unittest.mock import Mock

import napari
from napari_cocoutils._reader import coco_reader
from napari_cocoutils._widget import CocoWidget


# Test data path
SAMPLE_COCO_FILE = "/Users/santiago/switchdrive/boeck_lab_projects/cocoutils/test.json"


@pytest.fixture
def performance_coco_file():
    """Fixture for performance testing with real data."""
    coco_path = Path(SAMPLE_COCO_FILE)
    if not coco_path.exists():
        pytest.skip(f"Performance test file not found: {SAMPLE_COCO_FILE}")
    return str(coco_path)


def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


class TestLoadingPerformance:
    """Test file loading performance metrics."""
    
    def test_coco_file_loading_speed(self, performance_coco_file):
        """Test COCO file loading speed benchmarks."""
        # Warm-up run
        coco_reader(performance_coco_file)
        
        # Benchmark runs
        times = []
        for _ in range(3):
            start_time = time.perf_counter()
            result = coco_reader(performance_coco_file)
            end_time = time.perf_counter()
            
            assert result is not None
            times.append(end_time - start_time)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"Loading times: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
        
        # Performance requirements
        assert avg_time < 1.0, f"Average loading time too slow: {avg_time:.3f}s"
        assert max_time < 2.0, f"Worst-case loading time too slow: {max_time:.3f}s"
        
        # Count annotations for throughput
        num_annotations = len(result[0][0])
        throughput = num_annotations / avg_time
        print(f"Throughput: {throughput:.0f} annotations/second")
        
        assert throughput > 5000, f"Throughput too low: {throughput:.0f} ann/sec"
    
    def test_memory_usage_during_loading(self, performance_coco_file):
        """Test memory usage during file loading."""
        # Baseline memory
        baseline_memory = get_memory_usage()
        
        # Load file and measure memory
        result = coco_reader(performance_coco_file)
        peak_memory = get_memory_usage()
        
        memory_increase = peak_memory - baseline_memory
        num_annotations = len(result[0][0])
        memory_per_annotation = memory_increase / num_annotations * 1024  # KB per annotation
        
        print(f"Memory usage: {memory_increase:.1f}MB for {num_annotations} annotations")
        print(f"Memory per annotation: {memory_per_annotation:.3f}KB")
        
        # Memory requirements (should be reasonable)
        assert memory_increase < 50.0, f"Memory usage too high: {memory_increase:.1f}MB"
        assert memory_per_annotation < 10.0, f"Memory per annotation too high: {memory_per_annotation:.3f}KB"
        
        # Cleanup and check for memory leaks
        del result
        import gc
        gc.collect()
        
        final_memory = get_memory_usage()
        memory_leak = final_memory - baseline_memory
        
        # Allow some memory overhead but no major leaks
        assert memory_leak < 5.0, f"Potential memory leak: {memory_leak:.1f}MB retained"
    
    def test_repeated_loading_performance(self, performance_coco_file):
        """Test performance with repeated file loading."""
        times = []
        max_iterations = 5
        
        for i in range(max_iterations):
            start_time = time.perf_counter()
            result = coco_reader(performance_coco_file)
            end_time = time.perf_counter()
            
            times.append(end_time - start_time)
            
            # Verify data consistency across loads
            assert result is not None
            assert len(result) > 0
            
        # Performance should be consistent (no significant degradation)
        avg_time = sum(times) / len(times)
        std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
        
        print(f"Repeated loading: avg={avg_time:.3f}s, std_dev={std_dev:.3f}s")
        
        # Standard deviation should be small (consistent performance)
        assert std_dev < 0.1, f"Performance too inconsistent: {std_dev:.3f}s std_dev"


class TestVisualizationPerformance:
    """Test napari visualization performance."""
    
    def test_napari_layer_creation_speed(self, performance_coco_file):
        """Test napari layer creation performance."""
        pytest.importorskip("napari")
        
        # Load data first
        layer_data_list = coco_reader(performance_coco_file)
        shapes_data, metadata, layer_type = layer_data_list[0]
        
        # Create headless viewer
        viewer = napari.Viewer(show=False)
        
        try:
            # Benchmark layer creation
            start_time = time.perf_counter()
            layer = viewer.add_shapes(shapes_data, **metadata)
            end_time = time.perf_counter()
            
            creation_time = end_time - start_time
            num_shapes = len(shapes_data)
            
            print(f"Layer creation: {creation_time:.3f}s for {num_shapes} shapes")
            print(f"Shape creation rate: {num_shapes/creation_time:.0f} shapes/second")
            
            # Performance requirements
            assert creation_time < 5.0, f"Layer creation too slow: {creation_time:.3f}s"
            assert num_shapes/creation_time > 1000, "Shape creation rate too low"
            
            # Verify layer was created correctly
            assert len(viewer.layers) == 1
            assert layer.data is not None
            assert len(layer.data) == num_shapes
            
        finally:
            viewer.close()
    
    def test_layer_property_access_speed(self, performance_coco_file):
        """Test speed of accessing layer properties."""
        pytest.importorskip("napari")
        
        layer_data_list = coco_reader(performance_coco_file)
        shapes_data, metadata, layer_type = layer_data_list[0]
        
        viewer = napari.Viewer(show=False)
        
        try:
            layer = viewer.add_shapes(shapes_data, **metadata)
            
            # Test property access speed
            start_time = time.perf_counter()
            
            # Access various properties
            _ = layer.data
            _ = layer.properties
            _ = layer.face_color
            _ = layer.edge_color
            _ = len(layer.data)
            
            end_time = time.perf_counter()
            
            access_time = end_time - start_time
            print(f"Property access time: {access_time:.6f}s")
            
            # Should be very fast
            assert access_time < 0.1, f"Property access too slow: {access_time:.6f}s"
            
        finally:
            viewer.close()


class TestWidgetPerformance:
    """Test widget interaction performance."""
    
    def test_widget_initialization_speed(self):
        """Test widget initialization performance."""
        pytest.importorskip("napari")
        
        mock_viewer = Mock(spec=napari.Viewer)
        mock_viewer.layers = Mock()
        mock_viewer.add_shapes = Mock(return_value=Mock())
        
        # Benchmark widget creation
        start_time = time.perf_counter()
        widget = CocoWidget(mock_viewer)
        end_time = time.perf_counter()
        
        init_time = end_time - start_time
        print(f"Widget initialization: {init_time:.6f}s")
        
        # Should be very fast
        assert init_time < 0.1, f"Widget initialization too slow: {init_time:.6f}s"
        
        # Verify widget components
        assert widget.viewer is mock_viewer
        assert widget.file_manager is not None
        assert widget.category_controller is not None
    
    def test_large_dataset_widget_performance(self, performance_coco_file):
        """Test widget performance with large dataset."""
        pytest.importorskip("napari")
        
        mock_viewer = Mock(spec=napari.Viewer)
        mock_viewer.layers = Mock()
        mock_viewer.add_shapes = Mock(return_value=Mock())
        
        widget = CocoWidget(mock_viewer)
        
        # Benchmark file loading through widget
        start_time = time.perf_counter()
        widget.file_manager.load_file(performance_coco_file)
        end_time = time.perf_counter()
        
        load_time = end_time - start_time
        print(f"Widget file loading: {load_time:.3f}s")
        
        assert load_time < 2.0, f"Widget file loading too slow: {load_time:.3f}s"
        
        # Benchmark controller initialization
        start_time = time.perf_counter()
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        widget.visualization_manager.initialize_visualizer(widget.file_manager.coco_data)
        end_time = time.perf_counter()
        
        init_time = end_time - start_time
        print(f"Controller initialization: {init_time:.3f}s")
        
        assert init_time < 1.0, f"Controller initialization too slow: {init_time:.3f}s"
        
        # Test category operations speed
        categories = widget.category_controller.categories
        num_categories = len(categories)
        
        start_time = time.perf_counter()
        for cat_id in categories:
            widget.category_controller.toggle_category(cat_id, False)
            widget.category_controller.toggle_category(cat_id, True)
        end_time = time.perf_counter()
        
        toggle_time = end_time - start_time
        print(f"Category toggle operations: {toggle_time:.6f}s for {num_categories * 2} operations")
        
        assert toggle_time < 0.1, f"Category operations too slow: {toggle_time:.6f}s"
    
    def test_filtering_performance(self, performance_coco_file):
        """Test annotation filtering performance."""
        pytest.importorskip("napari")
        
        mock_viewer = Mock(spec=napari.Viewer)
        mock_viewer.layers = Mock()
        mock_viewer.add_shapes = Mock(return_value=Mock())
        
        widget = CocoWidget(mock_viewer)
        widget.file_manager.load_file(performance_coco_file)
        widget.category_controller.initialize_categories(widget.file_manager.coco_data)
        widget.navigation_controller.initialize_images(widget.file_manager.coco_data)
        
        # Test annotation count calculation speed
        coco_data = widget.file_manager.coco_data
        image_id = widget.navigation_controller.get_current_image_id()
        all_categories = widget.category_controller.get_selected_categories()
        
        start_time = time.perf_counter()
        count_info = widget.display_controller.get_annotation_count_info(
            coco_data, image_id, all_categories
        )
        end_time = time.perf_counter()
        
        count_time = end_time - start_time
        visible_count = count_info['visible']
        
        print(f"Annotation counting: {count_time:.6f}s for {visible_count} annotations")
        
        # Should be fast even with thousands of annotations
        assert count_time < 0.1, f"Annotation counting too slow: {count_time:.6f}s"
        
        # Test filtering with different category combinations
        categories = list(widget.category_controller.categories.keys())
        
        filter_times = []
        for i in range(1, min(len(categories), 4) + 1):
            selected_categories = categories[:i]
            
            start_time = time.perf_counter()
            count_info = widget.display_controller.get_annotation_count_info(
                coco_data, image_id, selected_categories
            )
            end_time = time.perf_counter()
            
            filter_times.append(end_time - start_time)
        
        avg_filter_time = sum(filter_times) / len(filter_times)
        print(f"Average filtering time: {avg_filter_time:.6f}s")
        
        assert avg_filter_time < 0.05, f"Filtering too slow: {avg_filter_time:.6f}s"


class TestMemoryEfficiency:
    """Test memory usage patterns and efficiency."""
    
    def test_memory_scaling(self, performance_coco_file):
        """Test how memory usage scales with data size."""
        # Load full dataset
        result = coco_reader(performance_coco_file)
        full_shapes = result[0][0]
        full_memory = get_memory_usage()
        
        # Test with subsets
        subset_sizes = [100, 500, 1000, 2000]
        memory_per_annotation = []
        
        for size in subset_sizes:
            if size >= len(full_shapes):
                continue
                
            # Create subset
            subset_shapes = full_shapes[:size]
            subset_metadata = {
                'properties': result[0][1]['properties'][:size],
                'face_color': result[0][1]['face_color'][:size],
                'edge_color': result[0][1]['edge_color'][:size],
                'shape_type': result[0][1]['shape_type'][:size],
                'name': f'Subset {size}'
            }
            
            subset_memory = get_memory_usage()
            memory_increase = subset_memory - full_memory
            memory_per_annotation.append(memory_increase / size * 1024)  # KB per annotation
        
        # Memory usage should scale roughly linearly
        if len(memory_per_annotation) > 1:
            variation = max(memory_per_annotation) - min(memory_per_annotation)
            avg_memory = sum(memory_per_annotation) / len(memory_per_annotation)
            
            print(f"Memory per annotation: {avg_memory:.3f}KB ± {variation:.3f}KB")
            
            # Variation should be reasonable (not exponential scaling)
            assert variation < avg_memory, "Memory usage doesn't scale linearly"
    
    def test_cleanup_efficiency(self, performance_coco_file):
        """Test memory cleanup after operations."""
        baseline_memory = get_memory_usage()
        
        # Perform operations
        for _ in range(3):
            result = coco_reader(performance_coco_file)
            del result
        
        import gc
        gc.collect()
        
        final_memory = get_memory_usage()
        memory_retained = final_memory - baseline_memory
        
        print(f"Memory retained after cleanup: {memory_retained:.1f}MB")
        
        # Should not retain significant memory
        assert memory_retained < 2.0, f"Too much memory retained: {memory_retained:.1f}MB"


def pytest_configure(config):
    """Configure pytest for performance tests."""
    # Add custom markers
    config.addinivalue_line("markers", "performance: mark test as performance test")


# Add performance marker to all tests in this module
pytestmark = pytest.mark.performance