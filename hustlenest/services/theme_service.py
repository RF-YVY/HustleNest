"""Theme management service for light/dark mode support."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

from ..data import settings_repository


# Dark theme stylesheet
DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
}

QMenuBar {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border-bottom: 1px solid #3d3d3d;
}

QMenuBar::item:selected {
    background-color: #404040;
}

QMenu {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
}

QMenu::item:selected {
    background-color: #404040;
}

QTabWidget::pane {
    border: 1px solid #3d3d3d;
    background-color: #252525;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #e0e0e0;
    padding: 8px 16px;
    border: 1px solid #3d3d3d;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #404040;
    border-bottom: 2px solid #0078d4;
}

QTabBar::tab:hover:!selected {
    background-color: #353535;
}

QTableView, QTableWidget, QTreeView, QListView {
    background-color: #252525;
    alternate-background-color: #2a2a2a;
    color: #e0e0e0;
    gridline-color: #3d3d3d;
    border: 1px solid #3d3d3d;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QTableView::item:hover, QTableWidget::item:hover {
    background-color: #353535;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #e0e0e0;
    padding: 6px;
    border: 1px solid #3d3d3d;
    font-weight: bold;
}

QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1084d8;
}

QPushButton:pressed {
    background-color: #006cbd;
}

QPushButton:disabled {
    background-color: #404040;
    color: #808080;
}

QPushButton[flat="true"], QPushButton:flat {
    background-color: transparent;
    color: #0078d4;
}

QPushButton[flat="true"]:hover, QPushButton:flat:hover {
    background-color: #353535;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    padding: 4px 8px;
    border-radius: 4px;
    selection-background-color: #0078d4;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #0078d4;
}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #252525;
    color: #606060;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #e0e0e0;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    selection-background-color: #0078d4;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #4a4a4a;
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5a5a5a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #4a4a4a;
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #5a5a5a;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: #e0e0e0;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #e0e0e0;
}

QCheckBox, QRadioButton {
    color: #e0e0e0;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #606060;
    border-radius: 3px;
    background-color: #2d2d2d;
}

QRadioButton::indicator {
    border-radius: 10px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #0078d4;
}

QLabel {
    color: #e0e0e0;
}

QToolTip {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    padding: 4px;
}

QProgressBar {
    background-color: #2d2d2d;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
}

QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 3px;
}

QSlider::groove:horizontal {
    height: 6px;
    background-color: #3d3d3d;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background-color: #0078d4;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background-color: #1084d8;
}

QTextBrowser {
    background-color: #252525;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

QMessageBox {
    background-color: #1e1e1e;
}

QMessageBox QLabel {
    color: #e0e0e0;
}

/* Chart styling for dark mode */
QChartView {
    background-color: #252525;
}

/* Splitter handle */
QSplitter::handle {
    background-color: #3d3d3d;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

/* Status bar */
QStatusBar {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border-top: 1px solid #3d3d3d;
}

/* Form layout labels */
QFormLayout QLabel {
    color: #b0b0b0;
}
"""

# Light theme stylesheet (mostly default with minor enhancements)
LIGHT_STYLESHEET = """
QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1084d8;
}

QPushButton:pressed {
    background-color: #006cbd;
}

QPushButton:disabled {
    background-color: #cccccc;
    color: #888888;
}

QPushButton[flat="true"], QPushButton:flat {
    background-color: transparent;
    color: #0078d4;
}

QPushButton[flat="true"]:hover, QPushButton:flat:hover {
    background-color: #e8e8e8;
}

QTabBar::tab:selected {
    border-bottom: 2px solid #0078d4;
}

QTableView, QTableWidget {
    alternate-background-color: #f5f5f5;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #f0f0f0;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #d0d0d0;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #0078d4;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

QProgressBar::chunk {
    background-color: #0078d4;
}
"""


class ThemeManager(QObject):
    """Manages application theme (light/dark mode)."""
    
    theme_changed = Signal(str)  # Emits "light" or "dark"
    
    _instance: Optional["ThemeManager"] = None
    
    def __init__(self) -> None:
        super().__init__()
        self._current_theme: str = "light"
    
    @classmethod
    def instance(cls) -> "ThemeManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance
    
    @property
    def current_theme(self) -> str:
        """Return the current theme name."""
        return self._current_theme
    
    @property
    def is_dark_mode(self) -> bool:
        """Return True if dark mode is active."""
        return self._current_theme == "dark"
    
    def load_saved_theme(self) -> None:
        """Load the theme from settings."""
        saved_theme = settings_repository.get_setting("app_theme")
        if saved_theme in ("light", "dark"):
            self._current_theme = saved_theme
        else:
            self._current_theme = "light"
        self._apply_theme()
    
    def set_theme(self, theme: str) -> None:
        """Set the application theme."""
        if theme not in ("light", "dark"):
            theme = "light"
        
        if theme == self._current_theme:
            return
        
        self._current_theme = theme
        settings_repository.set_setting("app_theme", theme)
        self._apply_theme()
        self.theme_changed.emit(theme)
    
    def toggle_theme(self) -> str:
        """Toggle between light and dark mode. Returns the new theme name."""
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.set_theme(new_theme)
        return new_theme
    
    def _apply_theme(self) -> None:
        """Apply the current theme to the application."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        
        if self._current_theme == "dark":
            app.setStyleSheet(DARK_STYLESHEET)
            self._apply_dark_palette(app)
        else:
            app.setStyleSheet(LIGHT_STYLESHEET)
            self._apply_light_palette(app)
    
    def _apply_dark_palette(self, app: QApplication) -> None:
        """Apply dark color palette."""
        palette = QPalette()
        
        # Window colors
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
        
        # Base colors (for input fields, etc.)
        palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 37))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(42, 42, 42))
        
        # Text colors
        palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
        
        # Button colors
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
        
        # Highlight colors
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        # Link colors
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 153, 255))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(153, 102, 204))
        
        # Tooltip colors
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(224, 224, 224))
        
        # Disabled colors
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(96, 96, 96))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(96, 96, 96))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(96, 96, 96))
        
        app.setPalette(palette)
    
    def _apply_light_palette(self, app: QApplication) -> None:
        """Apply light color palette (default system palette)."""
        app.setPalette(app.style().standardPalette())
    
    def get_chart_colors(self) -> dict:
        """Get chart-appropriate colors for the current theme."""
        if self._current_theme == "dark":
            return {
                "background": QColor(37, 37, 37),
                "text": QColor(224, 224, 224),
                "grid": QColor(61, 61, 61),
                "axis": QColor(160, 160, 160),
                "series": [
                    QColor(0, 120, 212),   # Blue
                    QColor(16, 124, 16),   # Green
                    QColor(234, 67, 53),   # Red
                    QColor(251, 188, 4),   # Yellow
                    QColor(153, 102, 204), # Purple
                    QColor(0, 172, 193),   # Cyan
                    QColor(255, 152, 0),   # Orange
                    QColor(233, 30, 99),   # Pink
                ],
            }
        else:
            return {
                "background": QColor(255, 255, 255),
                "text": QColor(0, 0, 0),
                "grid": QColor(220, 220, 220),
                "axis": QColor(100, 100, 100),
                "series": [
                    QColor(0, 120, 212),   # Blue
                    QColor(16, 124, 16),   # Green
                    QColor(234, 67, 53),   # Red
                    QColor(251, 188, 4),   # Yellow
                    QColor(103, 58, 183),  # Purple
                    QColor(0, 151, 167),   # Cyan
                    QColor(255, 152, 0),   # Orange
                    QColor(233, 30, 99),   # Pink
                ],
            }


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    return ThemeManager.instance()
