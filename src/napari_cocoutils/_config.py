"""
Configuration management for napari-cocoutils plugin.

This module handles plugin configuration, user preferences,
and default settings management.
"""

from typing import Dict, Any, Optional, Union
from pathlib import Path
import json
import os
from dataclasses import dataclass, asdict
import appdirs


@dataclass
class VisualizationConfig:
    """Configuration for visualization settings."""
    default_edge_width: float = 2.0
    default_opacity: float = 1.0
    max_annotations_display: int = 1000
    enable_caching: bool = True
    cache_size_limit: int = 100  # Number of cached items
    
    
@dataclass 
class UIConfig:
    """Configuration for user interface settings."""
    default_n_filter: int = 1000
    show_annotation_count: bool = True
    show_category_colors: bool = True
    enable_tooltips: bool = True
    compact_mode: bool = False
    

@dataclass
class PerformanceConfig:
    """Configuration for performance settings."""
    lazy_loading: bool = True
    background_processing: bool = False
    memory_limit_mb: int = 512
    gc_threshold: int = 50  # Must be aggressive due to large COCO datasets
    

@dataclass
class CocoPluginConfig:
    """Main configuration class for napari-cocoutils plugin."""
    visualization: VisualizationConfig = None
    ui: UIConfig = None
    performance: PerformanceConfig = None
    
    def __post_init__(self):
        if self.visualization is None:
            self.visualization = VisualizationConfig()
        if self.ui is None:
            self.ui = UIConfig()
        if self.performance is None:
            self.performance = PerformanceConfig()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CocoPluginConfig':
        return cls(
            visualization=VisualizationConfig(**data.get('visualization', {})),
            ui=UIConfig(**data.get('ui', {})),
            performance=PerformanceConfig(**data.get('performance', {}))
        )


class ConfigManager:
    """Manages plugin configuration loading, saving, and access."""
    
    def __init__(self, app_name: str = "napari-cocoutils"):
        self.app_name = app_name
        self._config_dir = Path(appdirs.user_config_dir(app_name))
        self._config_file = self._config_dir / "config.json"
        self._config: Optional[CocoPluginConfig] = None
        
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
    @property
    def config(self) -> CocoPluginConfig:
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def load_config(self) -> CocoPluginConfig:
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                return CocoPluginConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Error loading config, using defaults: {e}")
                
        return CocoPluginConfig()
    
    def save_config(self, config: Optional[CocoPluginConfig] = None) -> bool:
        """
        Save configuration to file.
        
        Parameters
        ----------
        config : CocoPluginConfig, optional
            Configuration to save. If None, saves current config.
            
        Returns
        -------
        bool
            True if saved successfully, False otherwise
        """
        if config is None:
            config = self.config
            
        try:
            with open(self._config_file, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            self._config = config
            return True
        except (OSError, TypeError) as e:
            print(f"Error saving config: {e}")
            return False
    
    def reset_to_defaults(self) -> CocoPluginConfig:
        """Reset configuration to defaults."""
        self._config = CocoPluginConfig()
        self.save_config(self._config)
        return self._config
    
    def update_config(self, **kwargs) -> bool:
        """
        Update configuration with new values.
        
        Parameters
        ----------
        **kwargs
            Configuration values to update
            
        Returns
        -------
        bool
            True if updated and saved successfully
        """
        config = self.config
        
        if 'visualization' in kwargs:
            for key, value in kwargs['visualization'].items():
                if hasattr(config.visualization, key):
                    setattr(config.visualization, key, value)
        
        if 'ui' in kwargs:
            for key, value in kwargs['ui'].items():
                if hasattr(config.ui, key):
                    setattr(config.ui, key, value)
        
        if 'performance' in kwargs:
            for key, value in kwargs['performance'].items():
                if hasattr(config.performance, key):
                    setattr(config.performance, key, value)
        
        return self.save_config(config)
    
    def get_config_path(self) -> Path:
        return self._config_file
    
    def export_config(self, export_path: Union[str, Path]) -> bool:
        """
        Export configuration to specified file.
        
        Parameters
        ----------
        export_path : str or Path
            Path to export configuration
            
        Returns
        -------
        bool
            True if exported successfully
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            return True
        except (OSError, TypeError) as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, import_path: Union[str, Path]) -> bool:
        """
        Import configuration from specified file.
        
        Parameters
        ----------
        import_path : str or Path
            Path to import configuration from
            
        Returns
        -------
        bool
            True if imported successfully
        """
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            config = CocoPluginConfig.from_dict(data)
            return self.save_config(config)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error importing config: {e}")
            return False


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> CocoPluginConfig:
    return get_config_manager().config


def apply_env_overrides(config: CocoPluginConfig) -> CocoPluginConfig:
    """Apply environment variable overrides to configuration."""
    if os.getenv('NAPARI_COCO_EDGE_WIDTH'):
        try:
            config.visualization.default_edge_width = float(os.getenv('NAPARI_COCO_EDGE_WIDTH'))
        except ValueError:
            pass
    
    if os.getenv('NAPARI_COCO_MAX_ANNOTATIONS'):
        try:
            config.visualization.max_annotations_display = int(os.getenv('NAPARI_COCO_MAX_ANNOTATIONS'))
        except ValueError:
            pass
    
    if os.getenv('NAPARI_COCO_DISABLE_CACHE'):
        config.visualization.enable_caching = os.getenv('NAPARI_COCO_DISABLE_CACHE').lower() != 'true'
    
    if os.getenv('NAPARI_COCO_DEFAULT_N_FILTER'):
        try:
            config.ui.default_n_filter = int(os.getenv('NAPARI_COCO_DEFAULT_N_FILTER'))
        except ValueError:
            pass
    
    if os.getenv('NAPARI_COCO_COMPACT_MODE'):
        config.ui.compact_mode = os.getenv('NAPARI_COCO_COMPACT_MODE').lower() == 'true'
    
    if os.getenv('NAPARI_COCO_MEMORY_LIMIT'):
        try:
            config.performance.memory_limit_mb = int(os.getenv('NAPARI_COCO_MEMORY_LIMIT'))
        except ValueError:
            pass
    
    if os.getenv('NAPARI_COCO_DISABLE_LAZY_LOADING'):
        config.performance.lazy_loading = os.getenv('NAPARI_COCO_DISABLE_LAZY_LOADING').lower() != 'true'
    
    return config


def get_effective_config() -> CocoPluginConfig:
    config = get_config()
    return apply_env_overrides(config)