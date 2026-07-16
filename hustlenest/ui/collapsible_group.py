"""Collapsible group box widget for dashboard sections."""
from __future__ import annotations

import json
from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..data import settings_repository


def _load_section_states() -> Dict[str, Dict[str, bool]]:
    """Load dashboard section states from settings."""
    try:
        raw = settings_repository.get_setting("dashboard_sections_json")
        if raw:
            return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _save_section_states(states: Dict[str, Dict[str, bool]]) -> None:
    """Save dashboard section states to settings."""
    settings_repository.set_setting("dashboard_sections_json", json.dumps(states))


class CollapsibleGroupBox(QFrame):
    """A collapsible/hideable group box for dashboard sections.
    
    Features:
    - Click header to collapse/expand content
    - Optional visibility toggle (hide entire section)
    - Persists state to settings
    """
    
    collapsed_changed = Signal(bool)
    visibility_changed = Signal(bool)
    
    def __init__(
        self,
        title: str,
        section_key: str,
        parent: Optional[QWidget] = None,
        *,
        show_visibility_toggle: bool = False,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._section_key = section_key
        self._is_collapsed = False
        self._content_widget: Optional[QWidget] = None
        
        # Load saved state
        states = _load_section_states()
        section_state = states.get(section_key, {})
        self._is_collapsed = section_state.get("collapsed", False)
        self._is_visible_section = section_state.get("visible", True)
        
        self._setup_ui(show_visibility_toggle)
        
    def _setup_ui(self, show_visibility_toggle: bool) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        
        # Header bar
        self._header = QWidget()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(8)
        self._header.setLayout(header_layout)
        self._header.setStyleSheet("""
            QWidget {
                background-color: palette(mid);
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
        """)
        
        # Collapse indicator
        self._collapse_indicator = QLabel("▼")
        self._collapse_indicator.setFixedWidth(16)
        self._collapse_indicator.setStyleSheet("font-size: 10px; font-weight: bold;")
        header_layout.addWidget(self._collapse_indicator)
        
        # Title label
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(self._title_label)
        
        header_layout.addStretch(1)
        
        # Visibility toggle button (optional)
        if show_visibility_toggle:
            self._visibility_btn = QPushButton("Hide")
            self._visibility_btn.setFixedWidth(50)
            self._visibility_btn.clicked.connect(self._toggle_section_visibility)
            header_layout.addWidget(self._visibility_btn)
        else:
            self._visibility_btn = None
        
        main_layout.addWidget(self._header)
        
        # Content container
        self._content_container = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(0)
        self._content_container.setLayout(content_layout)
        self._content_layout = content_layout
        main_layout.addWidget(self._content_container)
        
        # Connect header click
        self._header.mousePressEvent = self._on_header_clicked
        
        # Apply initial state
        self._apply_collapsed_state()
        
        # Handle section visibility
        if not self._is_visible_section:
            self.setVisible(False)
    
    def set_content(self, widget: QWidget) -> None:
        """Set the content widget for this collapsible section."""
        if self._content_widget:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        
        self._content_widget = widget
        self._content_layout.addWidget(widget)
        
    def _on_header_clicked(self, event) -> None:
        """Handle header click to toggle collapse state."""
        self._is_collapsed = not self._is_collapsed
        self._apply_collapsed_state()
        self._save_state()
        self.collapsed_changed.emit(self._is_collapsed)
    
    def _apply_collapsed_state(self) -> None:
        """Apply the current collapsed state to the UI."""
        self._content_container.setVisible(not self._is_collapsed)
        self._collapse_indicator.setText("▶" if self._is_collapsed else "▼")
        
        if self._is_collapsed:
            self._header.setStyleSheet("""
                QWidget {
                    background-color: palette(mid);
                    border-radius: 4px;
                }
            """)
        else:
            self._header.setStyleSheet("""
                QWidget {
                    background-color: palette(mid);
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
            """)
    
    def _toggle_section_visibility(self) -> None:
        """Toggle visibility of the entire section."""
        self._is_visible_section = not self._is_visible_section
        self.setVisible(self._is_visible_section)
        self._save_state()
        self.visibility_changed.emit(self._is_visible_section)
    
    def _save_state(self) -> None:
        """Save current state to settings."""
        states = _load_section_states()
        states[self._section_key] = {
            "collapsed": self._is_collapsed,
            "visible": self._is_visible_section,
        }
        _save_section_states(states)
    
    def set_collapsed(self, collapsed: bool) -> None:
        """Programmatically set collapsed state."""
        if self._is_collapsed != collapsed:
            self._is_collapsed = collapsed
            self._apply_collapsed_state()
            self._save_state()
    
    def set_section_visible(self, visible: bool) -> None:
        """Programmatically set section visibility."""
        if self._is_visible_section != visible:
            self._is_visible_section = visible
            self.setVisible(visible)
            self._save_state()
    
    def is_collapsed(self) -> bool:
        """Return whether the section is collapsed."""
        return self._is_collapsed
    
    def is_section_visible(self) -> bool:
        """Return whether the section is visible."""
        return self._is_visible_section
    
    @property
    def section_key(self) -> str:
        """Return the section key."""
        return self._section_key
    
    @property
    def title(self) -> str:
        """Return the section title."""
        return self._title


class DashboardSectionManager:
    """Manages dashboard section visibility and collapsed states."""
    
    # Define all dashboard sections
    SECTIONS = {
        "product_sales": "Product Sales Breakdown",
        "top_customers": "Top Customers",
        "notifications": "Notifications",
        "outstanding_orders": "Outstanding Orders",
        "completed_orders": "Completed Orders",
    }
    
    def __init__(self) -> None:
        self._sections: Dict[str, CollapsibleGroupBox] = {}
        self._callbacks: list[Callable[[], None]] = []
    
    def register_section(self, key: str, group_box: CollapsibleGroupBox) -> None:
        """Register a collapsible section."""
        self._sections[key] = group_box
    
    def get_section(self, key: str) -> Optional[CollapsibleGroupBox]:
        """Get a registered section by key."""
        return self._sections.get(key)
    
    def get_all_sections(self) -> Dict[str, CollapsibleGroupBox]:
        """Get all registered sections."""
        return self._sections.copy()
    
    def collapse_all(self) -> None:
        """Collapse all sections."""
        for section in self._sections.values():
            section.set_collapsed(True)
    
    def expand_all(self) -> None:
        """Expand all sections."""
        for section in self._sections.values():
            section.set_collapsed(False)
    
    def show_all(self) -> None:
        """Show all sections."""
        for section in self._sections.values():
            section.set_section_visible(True)
    
    def reset_to_defaults(self) -> None:
        """Reset all sections to default state (expanded and visible)."""
        for section in self._sections.values():
            section.set_collapsed(False)
            section.set_section_visible(True)
    
    def add_change_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be invoked when section states change."""
        self._callbacks.append(callback)
    
    def notify_change(self) -> None:
        """Notify all callbacks of a state change."""
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass


# Global section manager instance
_section_manager: Optional[DashboardSectionManager] = None


def get_section_manager() -> DashboardSectionManager:
    """Get the global dashboard section manager."""
    global _section_manager
    if _section_manager is None:
        _section_manager = DashboardSectionManager()
    return _section_manager
