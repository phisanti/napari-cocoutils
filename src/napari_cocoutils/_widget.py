"""
Main GUI widget for COCO visualization controls.

This module provides the primary user interface widget that allows users to:
- Browse and select COCO JSON files
- Control category visibility and colors
- Navigate between images in multi-image datasets
- Toggle visualization modes (overlay/masked)
"""

from typing import Dict, List, Optional
import numpy as np
from pathlib import Path
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QCheckBox, QComboBox, QFileDialog, QScrollArea,
    QLineEdit, QSlider, QSpinBox, QGroupBox, QSizePolicy
)
from qtpy.QtCore import Qt, Signal
from napari import Viewer
import napari

from ._utils import CocoError
from ._controllers import (
    CocoFileManager,
    CategoryController, 
    NavigationController,
    VisualizationManager,
    DisplayController
)


class CocoWidget(QWidget):
    """
    Main widget for COCO visualization controls in napari.
    
    This widget provides a user interface for loading COCO files,
    managing category visibility, and controlling visualization options.
    """
    
    def __init__(self, viewer: Viewer):
        """
        Initialize the COCO controls widget.
        
        Parameters
        ----------
        viewer : napari.Viewer
            The napari viewer instance this widget will control
        """
        super().__init__()
        self.viewer = viewer
        
        self.file_manager = CocoFileManager()
        self.category_controller = CategoryController()
        self.navigation_controller = NavigationController()
        self.visualization_manager = VisualizationManager(viewer)
        self.display_controller = DisplayController()
        
        self.category_checkboxes = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        title_label = QLabel("COCO Controls")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 5px;")
        main_layout.addWidget(title_label)
        
        file_section = self._create_file_browser_section()
        main_layout.addWidget(file_section)
        
        category_section = self._create_category_section()
        main_layout.addWidget(category_section)
        
        n_filter_section = self._create_n_filter_section()
        main_layout.addWidget(n_filter_section)
        
        viz_section = self._create_visualization_section()
        main_layout.addWidget(viz_section)
        
        nav_section = self._create_navigation_section()
        main_layout.addWidget(nav_section)
        
        main_layout.addStretch()
    
    def _create_file_browser_section(self) -> QWidget:
        """
        Create the file browser section of the widget.
        
        Returns
        -------
        QWidget
            Widget containing file selection controls
        """
        group = QGroupBox("File Input")
        layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("border: 1px solid gray; padding: 3px; background: white;")
        self.file_path_label.setMinimumHeight(25)
        
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.on_file_selected)
        browse_button.setMaximumWidth(80)
        
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(browse_button)
        layout.addLayout(file_layout)
        
        self.status_label = QLabel("Ready to load COCO file")
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        group.setLayout(layout)
        return group
    
    def _create_category_section(self) -> QWidget:
        """
        Create the category management section.
        
        Returns
        -------
        QWidget
            Widget containing category toggle controls
        """
        group = QGroupBox("Category Filters")
        layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_none_btn = QPushButton("Select None")
        self.select_all_btn.clicked.connect(self._select_all_categories)
        self.select_none_btn.clicked.connect(self._select_none_categories)
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.select_none_btn)
        layout.addLayout(button_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)
        
        self.category_widget = QWidget()
        self.category_layout = QVBoxLayout()
        self.category_widget.setLayout(self.category_layout)
        scroll_area.setWidget(self.category_widget)
        
        layout.addWidget(scroll_area)
        
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        
        group.setLayout(layout)
        return group
    
    def _create_n_filter_section(self) -> QWidget:
        """
        Create the N-filter section for annotation sampling.
        
        Returns
        -------
        QWidget
            Widget containing N-filter controls
        """
        group = QGroupBox("Display Options")
        layout = QVBoxLayout()
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Max annotations:"))
        
        self.n_filter_spinbox = QSpinBox()
        self.n_filter_spinbox.setMinimum(1)
        self.n_filter_spinbox.setMaximum(10000)
        self.n_filter_spinbox.setValue(1000)
        self.n_filter_spinbox.valueChanged.connect(self._on_n_filter_changed)
        
        self.annotation_count_label = QLabel("/ 0 total")
        
        filter_layout.addWidget(self.n_filter_spinbox)
        filter_layout.addWidget(self.annotation_count_label)
        layout.addLayout(filter_layout)
        
        # Add resample button
        self.resample_button = QPushButton("Resample")
        self.resample_button.clicked.connect(self._on_resample_clicked)
        self.resample_button.setEnabled(False)
        layout.addWidget(self.resample_button)
        
        self.n_filter_spinbox.setEnabled(False)
        
        group.setLayout(layout)
        return group
    
    def _create_visualization_section(self) -> QWidget:
        """
        Create the visualization mode section.
        
        Returns
        -------
        QWidget
            Widget containing visualization mode controls
        """
        group = QGroupBox("Visualization Mode")
        layout = QVBoxLayout()
        
        display_label = QLabel("Display:")
        display_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(display_label)
        
        self.show_bbox_checkbox = QCheckBox("Bounding Boxes")
        self.show_mask_checkbox = QCheckBox("Masks/Polygons")
        
        self.show_bbox_checkbox.setChecked(True)
        self.show_mask_checkbox.setChecked(True)
        
        self.show_bbox_checkbox.toggled.connect(self._on_display_mode_changed)
        self.show_mask_checkbox.toggled.connect(self._on_display_mode_changed)
        
        layout.addWidget(self.show_bbox_checkbox)
        layout.addWidget(self.show_mask_checkbox)
        
        self.show_bbox_checkbox.setEnabled(False)
        self.show_mask_checkbox.setEnabled(False)
        
        group.setLayout(layout)
        return group
    
    def _create_navigation_section(self) -> QWidget:
        """
        Create the image navigation section.
        
        Returns
        -------
        QWidget
            Widget containing navigation controls
        """
        group = QGroupBox("Multi-Image Navigation")
        layout = QVBoxLayout()
        
        image_layout = QHBoxLayout()
        image_layout.addWidget(QLabel("Image:"))
        
        self.image_combo = QComboBox()
        self.image_combo.currentIndexChanged.connect(self.on_image_changed)
        
        image_layout.addWidget(self.image_combo)
        layout.addLayout(image_layout)
        
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        
        self.prev_btn.clicked.connect(self._on_prev_image)
        self.next_btn.clicked.connect(self._on_next_image)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)
        
        self.image_combo.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        
        group.setLayout(layout)
        return group
    
    def on_file_selected(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, 
            "Select COCO JSON file", 
            "", 
            "JSON files (*.json);;All files (*.*)"
        )
        
        if not file_path:
            return
        self.status_label.setText("Loading COCO file...")
        self.status_label.setStyleSheet("color: orange; font-size: 11px;")
        
        try:
            # Add debugging information
            from ._utils import diagnose_coco_file
            print(f"Attempting to load COCO file: {file_path}")
            print("Diagnostic information:")
            print(diagnose_coco_file(file_path))
            print("-" * 50)
            
            coco_data = self.file_manager.load_file(file_path)
            
            self.category_controller.initialize_categories(coco_data)
            self.navigation_controller.initialize_images(coco_data)
            self.visualization_manager.initialize_visualizer(coco_data)
            
            # Initialize random seed for consistent sampling
            self.visualization_manager.set_random_seed(self.display_controller.random_seed)
            
            show_bbox, show_mask = self.display_controller.determine_default_display_modes(coco_data)
            self.show_bbox_checkbox.setChecked(show_bbox)
            self.show_mask_checkbox.setChecked(show_mask)
            self.display_controller.set_annotation_display_mode(show_bbox, show_mask)
            
            file_info = self.file_manager.get_file_info()
            self.file_path_label.setText(file_info['file_name'])
            
            self._update_category_controls()
            self._update_image_navigation()
            self._update_annotation_count()
            
            self._refresh_visualization()
            
            self.status_label.setText(
                f"✓ Loaded: {file_info['num_annotations']} annotations, "
                f"{file_info['num_images']} images"
            )
            self.status_label.setStyleSheet("color: green; font-size: 11px;")
            
            self._enable_controls()
            
        except CocoError as e:
            self.status_label.setText(f"✗ {e.user_message}")
            self.status_label.setStyleSheet("color: red; font-size: 11px;")
            self._reset_controllers()
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"Error loading COCO file: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            
            # Show more specific error information to user
            if "KeyError" in str(type(e)):
                self.status_label.setText(f"✗ Missing required field in COCO file: {error_msg}")
            elif "json" in error_msg.lower() or "JSONDecodeError" in str(type(e)):
                self.status_label.setText("✗ Invalid JSON format in COCO file")
            elif "FileNotFoundError" in str(type(e)):
                self.status_label.setText("✗ COCO file not found")
            elif "PermissionError" in str(type(e)):
                self.status_label.setText("✗ Permission denied accessing COCO file")
            else:
                self.status_label.setText(f"✗ Error loading COCO file: {error_msg[:50]}...")
            
            self.status_label.setStyleSheet("color: red; font-size: 11px;")
            self._reset_controllers()
    
    def _reset_controllers(self):
        self.file_manager = CocoFileManager()
        self.category_controller = CategoryController()
        self.navigation_controller = NavigationController()
        self.visualization_manager.cleanup()
        
    def on_category_toggled(self, category_id: int, enabled: bool):
        """
        Handle category visibility toggle.
        
        Parameters
        ----------
        category_id : int
            ID of the category being toggled
        enabled : bool
            New visibility state for the category
        """
        if not self.file_manager.is_loaded():
            return
        
        self.category_controller.toggle_category(category_id, enabled)
        
        self._refresh_visualization()
        
        self._update_annotation_count()
    
    def on_image_changed(self, image_idx: int):
        """
        Handle navigation to different image in dataset.
        
        Parameters
        ----------
        image_idx : int
            Index of the image to display
        """
        if not self.file_manager.is_loaded() or image_idx < 0:
            return
        
        if self.navigation_controller.navigate_to_image(image_idx):
            self._refresh_visualization()
            self._update_navigation_buttons()
    
    def _update_category_controls(self):
        if not self.file_manager.is_loaded():
            return
        for checkbox in self.category_checkboxes.values():
            checkbox.setParent(None)
        self.category_checkboxes.clear()
        
        categories = self.category_controller.categories
        if not categories:
            return
        
        coco_data = self.file_manager.coco_data
        
        for cat_id, category in categories.items():
            count = sum(1 for ann in coco_data.get('annotations', []) 
                       if ann.get('category_id') == cat_id)
            
            checkbox = QCheckBox(f"{category['name']} ({count})")
            checkbox.setChecked(self.category_controller.category_states[cat_id])
            checkbox.stateChanged.connect(
                lambda state, cid=cat_id: self.on_category_toggled(cid, state == Qt.Checked)
            )
            
            color = self.category_controller.get_category_color(cat_id)
            color_style = f"color: rgb({int(color[0]*255)}, {int(color[1]*255)}, {int(color[2]*255)});"
            checkbox.setStyleSheet(f"font-weight: bold; {color_style}")
            
            self.category_checkboxes[cat_id] = checkbox
            self.category_layout.addWidget(checkbox)
    
    def _refresh_visualization(self):
        if not self.file_manager.is_loaded():
            return
        
        try:
            current_image = self.navigation_controller.get_current_image()
            if not current_image:
                return
            
            image_id = current_image['id']
            image_filename = current_image.get('file_name', '')
            
            selected_categories = self.category_controller.get_selected_categories()
            
            n_filter = self.display_controller.n_filter_value
            self.visualization_manager.set_n_filter(n_filter)
            
            show_bbox = self.show_bbox_checkbox.isChecked()
            show_mask = self.show_mask_checkbox.isChecked()
            
            self.visualization_manager.refresh_visualization(
                image_id, selected_categories, image_filename, show_bbox, show_mask
            )
            
            self._update_annotation_count()
        
        except Exception as e:
            import traceback
            print(f"Error refreshing visualization: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            self.status_label.setText(f"✗ Visualization error: {str(e)[:40]}...")
            self.status_label.setStyleSheet("color: red; font-size: 11px;")
    
    def _update_image_navigation(self):
        if not self.file_manager.is_loaded():
            return
        
        images = self.navigation_controller.images
        self.image_combo.clear()
        for i, img in enumerate(images):
            self.image_combo.addItem(f"{i+1}: {img['file_name']}")
        
        has_multiple = self.navigation_controller.has_multiple_images()
        self.image_combo.setEnabled(has_multiple)
        self._update_navigation_buttons()
    
    def _update_annotation_count(self):
        if not self.file_manager.is_loaded():
            return
        
        current_image_id = self.navigation_controller.get_current_image_id()
        if current_image_id is None:
            return
        selected_categories = self.category_controller.get_selected_categories()
        count_info = self.display_controller.get_annotation_count_info(
            self.file_manager.coco_data, current_image_id, selected_categories
        )
        
        self.annotation_count_label.setText(
            f"/ {count_info['visible']} visible ({count_info['total']} total)"
        )
        
        if count_info['visible'] > 0:
            self.n_filter_spinbox.setMaximum(max(1, count_info['visible']))
            if self.display_controller.n_filter_value > count_info['visible']:
                self.display_controller.set_n_filter(min(1000, count_info['visible']))
                self.n_filter_spinbox.setValue(self.display_controller.n_filter_value)
    
    def _update_navigation_buttons(self):
        self.prev_btn.setEnabled(self.navigation_controller.can_go_previous())
        self.next_btn.setEnabled(self.navigation_controller.can_go_next())
    
    def _enable_controls(self):
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.n_filter_spinbox.setEnabled(True)
        self.resample_button.setEnabled(True)
        self.show_bbox_checkbox.setEnabled(True)
        self.show_mask_checkbox.setEnabled(True)
        
        if self.navigation_controller.has_multiple_images():
            self.image_combo.setEnabled(True)
            self._update_navigation_buttons()
    
    def _select_all_categories(self):
        self.category_controller.select_all()
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(True)
        self._refresh_visualization()
    
    def _select_none_categories(self):
        self.category_controller.select_none()
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(False)
        self._refresh_visualization()
    
    def _on_n_filter_changed(self, value):
        self.display_controller.set_n_filter(value)
        self._refresh_visualization()
    
    def _on_resample_clicked(self):
        """Handle resample button click."""
        self.display_controller.resample()
        # Pass the new seed to the visualization manager
        self.visualization_manager.set_random_seed(self.display_controller.random_seed)
        self._refresh_visualization()
    
    
    def _on_display_mode_changed(self):
        show_bbox = self.show_bbox_checkbox.isChecked()
        show_mask = self.show_mask_checkbox.isChecked()
        
        # Ensure at least one display mode is enabled
        if not show_bbox and not show_mask:
            # If user unchecked both, automatically enable the other one
            if self.sender() == self.show_bbox_checkbox:
                self.show_mask_checkbox.setChecked(True)
                show_mask = True
            else:
                self.show_bbox_checkbox.setChecked(True)
                show_bbox = True
        
        print(f"Display mode changed: bbox={show_bbox}, mask={show_mask}")
        self.display_controller.set_annotation_display_mode(show_bbox, show_mask)
        self._refresh_visualization()
    
    def _on_prev_image(self):
        if self.navigation_controller.go_previous():
            self.image_combo.setCurrentIndex(self.navigation_controller.current_image_idx)
            self._refresh_visualization()
            self._update_navigation_buttons()
    
    def _on_next_image(self):
        if self.navigation_controller.go_next():
            self.image_combo.setCurrentIndex(self.navigation_controller.current_image_idx)
            self._refresh_visualization()
            self._update_navigation_buttons()