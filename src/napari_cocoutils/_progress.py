"""
Progress indication utilities for napari-cocoutils plugin.

This module provides progress tracking and user feedback during
long-running operations like loading large COCO files.
"""

import time
import threading
from typing import Optional, Callable, Any, Dict
from contextlib import contextmanager
from dataclasses import dataclass, field
import logging

try:
    from qtpy.QtWidgets import QProgressDialog, QApplication
    from qtpy.QtCore import Qt, QTimer, Signal, QObject
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QProgressDialog = None
    QApplication = None
    Qt = None
    QTimer = None
    Signal = None
    QObject = None

logger = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Represents the current state of a progress operation."""
    current: int = 0
    total: int = 0
    message: str = ""
    started_at: float = field(default_factory=time.time)
    is_cancelled: bool = False
    
    @property
    def progress_percent(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.started_at
    
    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if self.current <= 0 or self.total <= 0:
            return None
        
        elapsed = self.elapsed_time
        rate = self.current / elapsed
        remaining_items = self.total - self.current
        
        return remaining_items / rate if rate > 0 else None


class ProgressReporter:
    """Base progress reporter interface."""
    
    def update(self, current: int, total: int, message: str = "") -> None:
        """Update progress state."""
        pass
    
    def finish(self, success: bool = True, message: str = "") -> None:
        """Complete progress reporting."""
        pass
    
    def is_cancelled(self) -> bool:
        """Check if operation was cancelled by user."""
        return False


class ConsoleProgressReporter(ProgressReporter):
    """Progress reporter that prints to console."""
    
    def __init__(self, show_eta: bool = True):
        self.show_eta = show_eta
        self.state = ProgressState()
        self.last_update = 0
        self.update_interval = 0.5  # Update every 500ms
    
    def update(self, current: int, total: int, message: str = "") -> None:
        self.state.current = current
        self.state.total = total
        self.state.message = message
        
        # Throttle console output
        now = time.time()
        if now - self.last_update < self.update_interval:
            return
        self.last_update = now
        
        progress_bar = self._create_progress_bar()
        eta_info = ""
        
        if self.show_eta and self.state.eta_seconds:
            eta_info = f" ETA: {self.state.eta_seconds:.1f}s"
        
        info = f"\r{progress_bar} {self.state.progress_percent:5.1f}%{eta_info}"
        if message:
            info += f" - {message}"
        
        print(info, end="", flush=True)
    
    def _create_progress_bar(self, width: int = 30) -> str:
        """Create ASCII progress bar."""
        if self.state.total <= 0:
            return "[" + "-" * width + "]"
        
        filled = int(width * self.state.current / self.state.total)
        bar = "[" + "=" * filled + ">" + " " * (width - filled - 1) + "]"
        return bar
    
    def finish(self, success: bool = True, message: str = "") -> None:
        status = "✓" if success else "✗"
        elapsed = self.state.elapsed_time
        final_msg = f"\n{status} Completed in {elapsed:.1f}s"
        
        if message:
            final_msg += f" - {message}"
        
        print(final_msg)


if QT_AVAILABLE:
    class QtProgressDialog(QObject):
        """Qt-based progress dialog with cancellation support."""
        
        cancelled = Signal()
        
        def __init__(self, title: str = "Loading...", parent=None):
            super().__init__()
            self.dialog = QProgressDialog(parent)
            self.dialog.setWindowTitle(title)
            self.dialog.setModal(True)
            self.dialog.setAutoClose(True)
            self.dialog.setAutoReset(False)
            self.dialog.canceled.connect(self._on_cancelled)
            
            # Timer for smooth updates
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self._update_display)
            self.update_timer.start(100)  # Update every 100ms
            
            self.state = ProgressState()
            self._is_cancelled = False
        
        def update(self, current: int, total: int, message: str = "") -> None:
            self.state.current = current
            self.state.total = total
            self.state.message = message
            
            # Update will happen via timer for smooth UI
        
        def _update_display(self):
            """Update the Qt dialog display."""
            if not self.dialog:
                return
            
            self.dialog.setMaximum(self.state.total)
            self.dialog.setValue(self.state.current)
            
            if self.state.message:
                self.dialog.setLabelText(self.state.message)
            
            # Process events to keep UI responsive
            QApplication.processEvents()
        
        def _on_cancelled(self):
            self._is_cancelled = True
            self.cancelled.emit()
        
        def is_cancelled(self) -> bool:
            return self._is_cancelled
        
        def finish(self, success: bool = True, message: str = "") -> None:
            self.update_timer.stop()
            
            if self.dialog:
                self.dialog.close()
                self.dialog = None
        
        def show(self):
            if self.dialog:
                self.dialog.show()
        
        def hide(self):
            if self.dialog:
                self.dialog.hide()


    class QtProgressReporter(ProgressReporter):
        """Progress reporter using Qt dialog."""
        
        def __init__(self, title: str = "Loading COCO data...", parent=None):
            self.progress_dialog = QtProgressDialog(title, parent)
            self.progress_dialog.show()
        
        def update(self, current: int, total: int, message: str = "") -> None:
            self.progress_dialog.update(current, total, message)
        
        def is_cancelled(self) -> bool:
            return self.progress_dialog.is_cancelled()
        
        def finish(self, success: bool = True, message: str = "") -> None:
            self.progress_dialog.finish(success, message)


class ProgressManager:
    """Manages progress reporting for operations."""
    
    def __init__(self):
        self._reporters: Dict[str, ProgressReporter] = {}
        self._default_reporter: Optional[str] = None
        self._lock = threading.RLock()
    
    def register_reporter(self, name: str, reporter: ProgressReporter, set_default: bool = False):
        """Register a progress reporter."""
        with self._lock:
            self._reporters[name] = reporter
            if set_default or not self._default_reporter:
                self._default_reporter = name
    
    def get_reporter(self, name: Optional[str] = None) -> Optional[ProgressReporter]:
        """Get a progress reporter by name."""
        with self._lock:
            if name:
                return self._reporters.get(name)
            elif self._default_reporter:
                return self._reporters.get(self._default_reporter)
            return None
    
    def create_reporter(self, title: str = "Processing...", 
                       reporter_type: str = "auto", 
                       parent=None) -> ProgressReporter:
        """Create appropriate progress reporter."""
        if reporter_type == "auto":
            if QT_AVAILABLE and QApplication.instance():
                reporter = QtProgressReporter(title, parent)
            else:
                reporter = ConsoleProgressReporter()
        elif reporter_type == "qt" and QT_AVAILABLE:
            reporter = QtProgressReporter(title, parent)
        elif reporter_type == "console":
            reporter = ConsoleProgressReporter()
        else:
            logger.warning(f"Unknown reporter type: {reporter_type}, using console")
            reporter = ConsoleProgressReporter()
        
        return reporter
    
    def remove_reporter(self, name: str):
        """Remove a registered reporter."""
        with self._lock:
            if name in self._reporters:
                reporter = self._reporters.pop(name)
                reporter.finish(success=False, message="Cancelled")
                
                if self._default_reporter == name:
                    self._default_reporter = next(iter(self._reporters), None)


# Global progress manager
_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    """Get the global progress manager instance."""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager


@contextmanager
def progress_context(title: str = "Processing...", 
                    reporter_type: str = "auto",
                    parent=None,
                    show_console_fallback: bool = True):
    """Context manager for progress reporting."""
    manager = get_progress_manager()
    
    try:
        reporter = manager.create_reporter(title, reporter_type, parent)
        yield reporter
        reporter.finish(success=True)
    except Exception as e:
        if 'reporter' in locals():
            reporter.finish(success=False, message=f"Error: {str(e)}")
        
        # Fallback to console if Qt fails and fallback enabled
        if show_console_fallback and reporter_type != "console":
            try:
                with progress_context(title, "console", parent, False) as fallback_reporter:
                    # Re-raise the original exception to continue processing
                    raise
            except:
                pass
        
        raise


def create_progress_callback(reporter: ProgressReporter) -> Callable[[int, int, str], None]:
    """Create a callback function for progress updates."""
    def callback(current: int, total: int, message: str = ""):
        reporter.update(current, total, message)
        
        # Check for cancellation
        if reporter.is_cancelled():
            raise KeyboardInterrupt("Operation cancelled by user")
    
    return callback


def estimate_file_processing_time(file_size_bytes: int, 
                                base_rate_mb_per_sec: float = 10.0) -> float:
    """Estimate processing time based on file size."""
    file_size_mb = file_size_bytes / (1024 * 1024)
    return file_size_mb / base_rate_mb_per_sec


def format_eta(seconds: float) -> str:
    """Format ETA in human-readable format."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


# Convenience functions
def console_progress(title: str = "Processing..."):
    """Quick console progress context."""
    return progress_context(title, "console")


if QT_AVAILABLE:
    def qt_progress(title: str = "Processing...", parent=None):
        """Quick Qt progress context."""
        return progress_context(title, "qt", parent)
else:
    def qt_progress(title: str = "Processing...", parent=None):
        """Fallback when Qt not available."""
        logger.warning("Qt not available, falling back to console progress")
        return progress_context(title, "console", parent)