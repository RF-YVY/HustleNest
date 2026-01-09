from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QDate, Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from ..models.order_models import AppSettings, CostComponent, NotificationMessage, Order, OrderItem, OrderReportRow, Product
from ..resources import get_app_icon_path
from ..services import order_service
from ..versioning import APP_VERSION, RELEASES_URL, REPOSITORY_URL, check_for_updates
from ..viewmodels.table_models import ListTableModel
from .cost_component_dialog import CostComponentEditorDialog
from .product_manager import ProductManagerDialog
from .invoice_manager import InvoiceManagerDialog


APP_NAME = "HustleNest"

STATE_CODE_TO_NAME: Dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}

US_STATES_GEOJSON_URL = (
    "https://cdn.jsdelivr.net/gh/PublicaMundi/MappingAPI@master/data/geojson/us-states.json"
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(QIcon(str(get_app_icon_path())))
        self.resize(1280, 820)

        self._pending_items: List[OrderItem] = []
        self._products_cache: List[Product] = []
        self._recent_orders_cache: List[Order] = []
        self._selected_order: Optional[Order] = None
        self._editing_order_id: Optional[int] = None
        self._current_cost_components: List[CostComponent] = []
        self._app_settings: AppSettings = order_service.get_app_settings()
        self._status_options: List[str] = order_service.list_order_statuses()
        self._product_status_options: List[str] = order_service.list_product_statuses()
        self._product_manager_dialog: Optional[ProductManagerDialog] = None

        self._tab_widget = QTabWidget()
        self.setCentralWidget(self._tab_widget)

        self._dashboard_tab = QWidget()
        self._orders_tab = QWidget()
        self._reports_tab = QWidget()
        self._history_tab = QWidget()
        self._products_tab = QWidget()
        self._settings_tab = QWidget()
        self._graphs_tab = QWidget()
        self._about_tab = QWidget()
        self._map_tab = QWidget()

        self._tab_widget.addTab(self._dashboard_tab, "Dashboard")
        self._tab_widget.addTab(self._orders_tab, "Orders")
        self._tab_widget.addTab(self._reports_tab, "Reports")
        self._tab_widget.addTab(self._history_tab, "History")
        self._tab_widget.addTab(self._products_tab, "Products")
        self._tab_widget.addTab(self._graphs_tab, "Graphs")
        self._tab_widget.addTab(self._map_tab, "Map")
        self._tab_widget.addTab(self._settings_tab, "Settings")
        self._tab_widget.addTab(self._about_tab, "About")

        self._total_sales_label: QLabel
        self._net_sales_label: QLabel
        self._outstanding_label: QLabel
        self._completed_label: QLabel
        self._product_model: ListTableModel
        self._customer_model: ListTableModel
        self._forecast_model: ListTableModel
        self._outstanding_model: ListTableModel
        self._completed_model: ListTableModel
        self._notifications_model: ListTableModel
        self._business_title_label: QLabel
        self._dashboard_logo_label: QLabel
        self._dashboard_brand_widget: QWidget
        self._dashboard_brand_top: QWidget
        self._dashboard_brand_bottom: QWidget
        self._dashboard_brand_top_layout: QHBoxLayout
        self._dashboard_brand_bottom_layout: QHBoxLayout
        self._dashboard_brand_layout: QHBoxLayout

        self._order_number_input: QLineEdit
        self._customer_name_input: QLineEdit
        self._customer_address_input: QTextEdit
        self._order_notes_input: QTextEdit
        self._order_date_input: QDateEdit
        self._ship_date_input: QDateEdit
        self._target_completion_input: QDateEdit
        self._status_input: QComboBox
        self._paid_checkbox: QCheckBox
        self._product_combo: QComboBox
        self._product_description_input: QLineEdit
        self._quantity_input: QSpinBox
        self._unit_price_input: QDoubleSpinBox
        self._base_cost_input: QDoubleSpinBox
        self._line_price_type: QComboBox
        self._add_item_button: QPushButton
        self._edit_item_button: QPushButton
        self._cancel_edit_item_button: QPushButton
        self._remove_item_button: QPushButton
        self._cost_summary_label: QLabel
        self._margin_preview_label: QLabel
        self._pending_items_model: ListTableModel
        self._pending_items_table: QTableView
        self._recent_orders_model: ListTableModel
        self._recent_orders_table: QTableView
        self._customer_table: QTableView
        self._notifications_table: QTableView
        self._order_status_label: QLabel
        self._carrier_input: QLineEdit
        self._tracking_input: QLineEdit
        self._cancel_order_button: QPushButton
        self._delete_order_button: QPushButton
        self._map_status_label: QLabel
        self._map_view: QWebEngineView
        self._geocode_cache: Dict[str, Tuple[float, float]] = {}
        self._map_lines_checkbox: QCheckBox
        self._map_line_style: QComboBox
        self._map_line_color: QComboBox
        self._map_line_pattern: QComboBox
        self._map_base_layer_combo: QComboBox
        self._map_territory_checkbox: QCheckBox

        self._report_start_date: QDateEdit
        self._report_end_date: QDateEdit
        self._report_range_input: QComboBox
        self._report_model: ListTableModel
        self._report_status_label: QLabel
        self._reports_header_label: QLabel
        self._report_summary_label: QLabel
        self._report_export_button: QPushButton
        self._editing_line_index: Optional[int] = None
        self._current_report_rows: List[OrderReportRow] = []

        self._history_model: ListTableModel
        self._history_table: QTableView
        self._history_order_filter: QLineEdit
        self._history_start_filter: QDateEdit
        self._history_end_filter: QDateEdit
        self._history_status_label: QLabel

        self._business_name_input: QLineEdit
        self._low_inventory_input: QSpinBox
        self._order_number_format_input: QLineEdit
        self._order_number_next_input: QSpinBox
        self._settings_status_label: QLabel
        self._show_business_name_checkbox: QCheckBox
        self._logo_path_input: QLineEdit
        self._logo_alignment_combo: QComboBox
        self._logo_size_input: QSpinBox
        self._home_city_input: QLineEdit
        self._home_state_input: QLineEdit
        self._tax_rate_input: QDoubleSpinBox
        self._tax_show_invoice_checkbox: QCheckBox
        self._tax_include_total_checkbox: QCheckBox

        self._chart_view: QChartView
        self._completed_table: QTableView
        self._update_status_label: QLabel

        self._build_dashboard_tab()
        self._build_orders_tab()
        self._build_reports_tab()
        self._build_history_tab()
        self._build_products_tab()
        self._build_graphs_tab()
        self._build_map_tab()
        self._build_settings_tab()
        self._build_about_tab()

        self._refresh_products()
        self.refresh_dashboard()
        self._load_recent_orders()
        QTimer.singleShot(0, self._check_for_updates)
        self._run_report()
        self._load_history()
        self._update_graphs()
        self._refresh_map()

    # Dashboard tab
    def _build_dashboard_tab(self) -> None:
        layout = QVBoxLayout()
        self._dashboard_tab.setLayout(layout)

        self._dashboard_brand_top = QWidget()
        self._dashboard_brand_top_layout = QHBoxLayout()
        self._dashboard_brand_top_layout.setContentsMargins(0, 0, 0, 0)
        self._dashboard_brand_top_layout.setSpacing(0)
        self._dashboard_brand_top.setLayout(self._dashboard_brand_top_layout)
        layout.addWidget(self._dashboard_brand_top)
        self._dashboard_brand_top.setVisible(False)

        self._dashboard_brand_widget = QWidget()
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(12)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dashboard_brand_layout = brand_layout
        self._dashboard_brand_widget.setLayout(brand_layout)

        self._business_title_label = QLabel(self._app_settings.business_name)
        self._business_title_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        brand_layout.addWidget(self._business_title_label)

        self._dashboard_logo_label = QLabel()
        self._dashboard_logo_label.setVisible(False)
        self._dashboard_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(self._dashboard_logo_label)

        header_layout = QHBoxLayout()
        layout.addLayout(header_layout)

        self._total_sales_label = QLabel("Total Sales: $0.00")
        self._total_sales_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        header_layout.addWidget(self._total_sales_label)

        self._net_sales_label = QLabel("Net Revenue: $0.00 (Freebies: $0.00)")
        self._net_sales_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        header_layout.addWidget(self._net_sales_label)

        self._outstanding_label = QLabel("Outstanding Orders: 0")
        self._outstanding_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        header_layout.addWidget(self._outstanding_label)

        self._completed_label = QLabel("Completed Orders: 0")
        self._completed_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        header_layout.addWidget(self._completed_label)
        header_layout.addStretch(1)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_dashboard)
        header_layout.addWidget(refresh_button)

        body_layout = QHBoxLayout()
        layout.addLayout(body_layout)

        self._product_model = ListTableModel(
            (
                ("Product", lambda row: getattr(row, "product_name", "")),
                ("Quantity", lambda row: getattr(row, "total_quantity", "")),
                ("Total Sales", lambda row: f"${getattr(row, 'total_sales', 0):,.2f}"),
            )
        )
        self._product_table = QTableView()
        self._product_table.setModel(self._product_model)
        self._configure_table(self._product_table)

        self._customer_model = ListTableModel(
            (
                ("Customer", lambda row: getattr(row, "customer_name", "")),
                ("Orders", lambda row: getattr(row, "order_count", "")),
                ("Total Sales", lambda row: f"${getattr(row, 'total_sales', 0):,.2f}"),
                ("Avg Order", lambda row: f"${getattr(row, 'average_order', 0):,.2f}"),
            )
        )
        self._customer_table = QTableView()
        self._customer_table.setModel(self._customer_model)
        self._configure_table(self._customer_table)

        self._notifications_model = ListTableModel(
            (
                ("Category", lambda row: getattr(row, "category", "")),
                ("Severity", lambda row: getattr(row, "severity", "").title()),
                ("Message", lambda row: getattr(row, "message", "")),
            )
        )
        self._notifications_table = QTableView()
        self._notifications_table.setModel(self._notifications_model)
        self._configure_table(self._notifications_table)

        metrics_panel = QWidget()
        metrics_layout = QVBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(12)
        metrics_panel.setLayout(metrics_layout)
        metrics_layout.addWidget(self._wrap_group("Product Sales Breakdown", self._product_table))
        metrics_layout.addWidget(self._wrap_group("Top Customers", self._customer_table))
        metrics_layout.addWidget(self._wrap_group("Notifications", self._notifications_table))

        body_layout.addWidget(metrics_panel, stretch=2)

        self._outstanding_model = ListTableModel(
            (
                ("Order #", lambda row: getattr(row, "order_number", "")),
                ("Customer", lambda row: getattr(row, "customer_name", "")),
                (
                    "Order Date",
                    lambda row: getattr(row, "order_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "order_date", None)
                    else "",
                ),
                (
                    "Target Date",
                    lambda row: getattr(row, "target_completion_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "target_completion_date", None)
                    else "",
                ),
                (
                    "Total",
                    lambda row, mw=self: f"${getattr(row, 'total_amount', 0.0) + (getattr(row, 'tax_amount', 0.0) if getattr(mw._app_settings, 'tax_add_to_total', False) else 0.0):,.2f}",
                ),
                ("Status", lambda row: getattr(row, "status", "")),
                ("Carrier", lambda row: getattr(row, "carrier", "")),
                ("Tracking #", lambda row: getattr(row, "tracking_number", "")),
            )
        )
        self._outstanding_table = QTableView()
        self._outstanding_table.setModel(self._outstanding_model)
        self._configure_table(self._outstanding_table)

        self._completed_model = ListTableModel(
            (
                ("Order #", lambda row: getattr(row, "order_number", "")),
                ("Customer", lambda row: getattr(row, "customer_name", "")),
                (
                    "Ship Date",
                    lambda row: getattr(row, "ship_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "ship_date", None)
                    else "",
                ),
                (
                    "Target Date",
                    lambda row: getattr(row, "target_completion_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "target_completion_date", None)
                    else "",
                ),
                (
                    "Total",
                    lambda row, mw=self: f"${getattr(row, 'total_amount', 0.0) + (getattr(row, 'tax_amount', 0.0) if getattr(mw._app_settings, 'tax_add_to_total', False) else 0.0):,.2f}",
                ),
                ("Carrier", lambda row: getattr(row, "carrier", "")),
                ("Tracking #", lambda row: getattr(row, "tracking_number", "")),
            )
        )
        self._completed_table = QTableView()
        self._completed_table.setModel(self._completed_model)
        self._configure_table(self._completed_table)

        orders_panel = QWidget()
        orders_layout = QVBoxLayout()
        orders_layout.setContentsMargins(0, 0, 0, 0)
        orders_layout.setSpacing(12)
        orders_panel.setLayout(orders_layout)
        orders_layout.addWidget(self._wrap_group("Outstanding Orders", self._outstanding_table))
        orders_layout.addWidget(self._wrap_group("Completed Orders", self._completed_table))

        body_layout.addWidget(orders_panel, stretch=3)

        self._dashboard_brand_bottom = QWidget()
        self._dashboard_brand_bottom_layout = QHBoxLayout()
        self._dashboard_brand_bottom_layout.setContentsMargins(0, 0, 0, 0)
        self._dashboard_brand_bottom_layout.setSpacing(0)
        self._dashboard_brand_bottom.setLayout(self._dashboard_brand_bottom_layout)
        layout.addWidget(self._dashboard_brand_bottom)
        self._dashboard_brand_bottom.setVisible(False)

    # Orders tab
    def _build_orders_tab(self) -> None:
        layout = QVBoxLayout()
        self._orders_tab.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self._order_number_input = QLineEdit()
        self._order_number_input.setText(order_service.preview_next_order_number())
        form_layout.addRow("Order Number", self._order_number_input)

        self._customer_name_input = QLineEdit()
        form_layout.addRow("Customer Name", self._customer_name_input)

        self._customer_address_input = QTextEdit()
        self._customer_address_input.setFixedHeight(80)
        form_layout.addRow("Customer Address", self._customer_address_input)

        self._order_date_input = QDateEdit()
        self._order_date_input.setCalendarPopup(True)
        self._order_date_input.setDate(QDate.currentDate())
        form_layout.addRow("Order Date", self._order_date_input)

        self._ship_date_input = QDateEdit()
        self._ship_date_input.setCalendarPopup(True)
        self._ship_date_input.setSpecialValueText("Not Set")
        self._ship_date_input.setDate(QDate.currentDate())
        form_layout.addRow("Ship Date", self._ship_date_input)

        self._target_completion_input = QDateEdit()
        self._target_completion_input.setCalendarPopup(True)
        self._target_completion_input.setSpecialValueText("No Target")
        self._target_completion_input.setDate(QDate.currentDate())
        form_layout.addRow("Target Complete By", self._target_completion_input)

        self._status_input = QComboBox()
        if self._status_options:
            self._status_input.addItems(self._status_options)
        form_layout.addRow("Status", self._status_input)
        self._status_input.currentTextChanged.connect(self._on_status_changed)

        self._paid_checkbox = QCheckBox("Mark order as paid")
        self._paid_checkbox.stateChanged.connect(self._on_paid_checkbox_changed)
        form_layout.addRow("", self._paid_checkbox)

        self._carrier_input = QLineEdit()
        self._carrier_input.setPlaceholderText("Carrier (e.g., UPS)")
        form_layout.addRow("Carrier", self._carrier_input)

        self._tracking_input = QLineEdit()
        self._tracking_input.setPlaceholderText("Tracking Number")
        form_layout.addRow("Tracking #", self._tracking_input)

        self._order_notes_input = QTextEdit()
        self._order_notes_input.setPlaceholderText("Internal notes for this order")
        self._order_notes_input.setFixedHeight(80)
        form_layout.addRow("Notes", self._order_notes_input)

        product_selection_layout = QHBoxLayout()
        layout.addLayout(product_selection_layout)

        def make_labeled_container(label_text: str, widget: QWidget) -> QWidget:
            container = QWidget()
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            label = QLabel(label_text)
            column.addWidget(label)
            column.addWidget(widget)
            container.setLayout(column)
            return container

        self._product_combo = QComboBox()
        self._product_combo.setEditable(True)
        self._product_combo.setPlaceholderText("Select or type a product")
        self._product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._product_combo.setToolTip("Choose a product by name or SKU to populate the line item.")
        self._product_combo.currentIndexChanged.connect(self._on_product_combo_index_changed)
        product_selection_layout.addWidget(
            make_labeled_container("Select Product", self._product_combo),
            stretch=3,
        )

        self._product_description_input = QLineEdit()
        self._product_description_input.setPlaceholderText("Line item description")
        self._product_description_input.setToolTip("Optional description that appears on the invoice line item.")
        product_selection_layout.addWidget(
            make_labeled_container("Line Description", self._product_description_input),
            stretch=3,
        )

        self._quantity_input = QSpinBox()
        self._quantity_input.setMinimum(1)
        self._quantity_input.setMaximum(1_000_000)
        self._quantity_input.setValue(1)
        self._quantity_input.setToolTip("Number of units to include for this product.")
        self._quantity_input.valueChanged.connect(lambda _value: self._refresh_margin_preview())
        product_selection_layout.addWidget(make_labeled_container("Quantity", self._quantity_input))

        self._unit_price_input = QDoubleSpinBox()
        self._unit_price_input.setPrefix("$")
        self._unit_price_input.setDecimals(2)
        self._unit_price_input.setMaximum(1_000_000)
        self._unit_price_input.setValue(0.00)
        self._unit_price_input.setToolTip("Customer-facing unit price for this line item.")
        self._unit_price_input.valueChanged.connect(self._on_unit_price_changed)
        product_selection_layout.addWidget(
            make_labeled_container("Unit Price (customer)", self._unit_price_input)
        )

        self._base_cost_input = QDoubleSpinBox()
        self._base_cost_input.setPrefix("$")
        self._base_cost_input.setDecimals(2)
        self._base_cost_input.setMaximum(1_000_000)
        self._base_cost_input.setValue(0.00)
        self._base_cost_input.setToolTip("Default product cost used for margin calculations.")
        self._base_cost_input.valueChanged.connect(self._refresh_margin_preview)
        product_selection_layout.addWidget(
            make_labeled_container("Base Cost (default)", self._base_cost_input)
        )

        self._line_price_type = QComboBox()
        self._line_price_type.addItems(["Standard", "FREEBIE"])
        self._line_price_type.setCurrentIndex(0)
        self._line_price_type.currentTextChanged.connect(self._on_price_type_changed)
        product_selection_layout.addWidget(self._line_price_type)

        self._add_item_button = QPushButton("Add Item")
        self._add_item_button.clicked.connect(self._handle_add_item)
        product_selection_layout.addWidget(self._add_item_button)

        self._edit_item_button = QPushButton("Edit Selected")
        self._edit_item_button.clicked.connect(self._handle_edit_item)
        self._edit_item_button.setEnabled(False)
        product_selection_layout.addWidget(self._edit_item_button)

        self._cancel_edit_item_button = QPushButton("Cancel Edit")
        self._cancel_edit_item_button.clicked.connect(self._handle_cancel_item_edit)
        self._cancel_edit_item_button.setVisible(False)
        product_selection_layout.addWidget(self._cancel_edit_item_button)

        self._remove_item_button = QPushButton("Remove Selected")
        self._remove_item_button.clicked.connect(self._handle_remove_item)
        self._remove_item_button.setEnabled(False)
        product_selection_layout.addWidget(self._remove_item_button)

        manage_products_button = QPushButton("Manage Products")
        manage_products_button.clicked.connect(self._open_product_manager)
        product_selection_layout.addWidget(manage_products_button)

        cost_layout = QHBoxLayout()
        layout.addLayout(cost_layout)

        self._cost_components_button = QPushButton("Extra Costs…")
        self._cost_components_button.clicked.connect(self._open_cost_component_editor)
        cost_layout.addWidget(self._cost_components_button)

        self._cost_summary_label = QLabel("Extras: $0.00")
        cost_layout.addWidget(self._cost_summary_label)

        self._margin_preview_label = QLabel("Unit Cost: $0.00 | Profit/unit: $0.00 | Margin: --")
        cost_layout.addWidget(self._margin_preview_label)

        cost_layout.addStretch(1)

        items_layout = QHBoxLayout()
        layout.addLayout(items_layout, stretch=1)

        self._pending_items_model = ListTableModel(
            (
                ("Product", lambda row: getattr(row, "product_name", "")),
                ("SKU", lambda row: getattr(row, "product_sku", "")),
                ("Description", lambda row: getattr(row, "product_description", "")),
                ("Quantity", lambda row: getattr(row, "quantity", "")),
                ("Unit Price", lambda row: f"${getattr(row, 'unit_price', 0):,.2f}"),
                ("Unit Cost", lambda row: f"${getattr(row, 'unit_cost', 0):,.2f}"),
                ("Line Cost", lambda row: f"${getattr(row, 'line_cost', 0):,.2f}"),
                ("Line Total", lambda row: f"${getattr(row, 'line_total', 0):,.2f}"),
                ("Profit", lambda row: f"${getattr(row, 'line_profit', 0):,.2f}"),
                (
                    "Margin",
                    lambda row: f"{getattr(row, 'margin', 0) * 100:,.1f}%"
                    if getattr(row, "line_total", 0) else "--",
                ),
                ("Adjustments", lambda row: getattr(row, "adjustment_summary", "")),
            )
        )
        self._pending_items_table = QTableView()
        self._pending_items_table.setModel(self._pending_items_model)
        self._configure_table(self._pending_items_table)
        pending_selection = self._pending_items_table.selectionModel()
        if pending_selection is not None:
            pending_selection.selectionChanged.connect(self._on_pending_items_selection_changed)
        self._update_item_action_buttons()

        items_layout.addWidget(self._wrap_group("Order Items", self._pending_items_table), stretch=2)

        self._recent_orders_model = ListTableModel(
            (
                ("Order #", lambda row: getattr(row, "order_number", "")),
                ("Customer", lambda row: getattr(row, "customer_name", "")),
                ("Items", lambda row, mw=self: mw._format_order_items_brief(row)),
                (
                    "Order Date",
                    lambda row: getattr(row, "order_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "order_date", None)
                    else "",
                ),
                (
                    "Target Date",
                    lambda row: getattr(row, "target_completion_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "target_completion_date", None)
                    else "",
                ),
                ("Status", lambda row: getattr(row, "status", "")),
                ("Carrier", lambda row: getattr(row, "carrier", "")),
                ("Tracking #", lambda row: getattr(row, "tracking_number", "")),
                (
                    "Total",
                    lambda row, mw=self: f"${getattr(row, 'total_amount', 0.0) + (getattr(row, 'tax_amount', 0.0) if getattr(mw._app_settings, 'tax_add_to_total', False) else 0.0):,.2f}",
                ),
            )
        )
        self._recent_orders_table = QTableView()
        self._recent_orders_table.setModel(self._recent_orders_model)
        self._configure_table(self._recent_orders_table)
        items_layout.addWidget(self._wrap_group("Recent Orders", self._recent_orders_table), stretch=3)

        recent_selection = self._recent_orders_table.selectionModel()
        if recent_selection is not None:
            recent_selection.currentChanged.connect(self._on_recent_order_selection_changed)

        controls_layout = QHBoxLayout()
        layout.addLayout(controls_layout)

        new_order_button = QPushButton("New Order")
        new_order_button.clicked.connect(self._handle_new_order)
        controls_layout.addWidget(new_order_button)

        save_button = QPushButton("Save Order")
        save_button.clicked.connect(self._handle_save_order)
        controls_layout.addWidget(save_button)

        refresh_orders_button = QPushButton("Refresh Orders")
        refresh_orders_button.clicked.connect(self._load_recent_orders)
        controls_layout.addWidget(refresh_orders_button)

        self._export_invoice_button = QPushButton("Export Invoice")
        self._export_invoice_button.clicked.connect(self._handle_export_invoice)
        self._export_invoice_button.setEnabled(False)
        controls_layout.addWidget(self._export_invoice_button)

        self._cancel_order_button = QPushButton("Cancel Order")
        self._cancel_order_button.clicked.connect(self._handle_cancel_order)
        self._cancel_order_button.setEnabled(False)
        controls_layout.addWidget(self._cancel_order_button)

        self._delete_order_button = QPushButton("Delete Order")
        self._delete_order_button.clicked.connect(self._handle_delete_order)
        self._delete_order_button.setEnabled(False)
        controls_layout.addWidget(self._delete_order_button)

        controls_layout.addStretch(1)

        self._order_status_label = QLabel()
        controls_layout.addWidget(self._order_status_label)
        self._update_cost_summary()

    # Reports tab
    def _build_reports_tab(self) -> None:
        layout = QVBoxLayout()
        self._reports_tab.setLayout(layout)

        self._reports_header_label = QLabel()
        self._reports_header_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self._reports_header_label)

        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        self._report_range_input = QComboBox()
        self._report_range_input.addItem("This Week", "week")
        self._report_range_input.addItem("This Month", "month")
        self._report_range_input.addItem("This Year", "year")
        self._report_range_input.addItem("All Time", "all")
        self._report_range_input.addItem("Custom Range", "custom")
        self._report_range_input.currentIndexChanged.connect(self._on_report_range_changed)
        filter_layout.addWidget(self._report_range_input)

        self._report_start_date = QDateEdit()
        self._report_start_date.setCalendarPopup(True)
        self._report_start_date.setSpecialValueText("Start Date")
        self._report_start_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self._report_start_date)

        self._report_end_date = QDateEdit()
        self._report_end_date.setCalendarPopup(True)
        self._report_end_date.setSpecialValueText("End Date")
        self._report_end_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self._report_end_date)

        run_button = QPushButton("Run Report")
        run_button.clicked.connect(self._run_report)
        filter_layout.addWidget(run_button)

        self._report_export_button = QPushButton("Export CSV")
        self._report_export_button.setEnabled(False)
        self._report_export_button.clicked.connect(self._handle_export_report)
        filter_layout.addWidget(self._report_export_button)

        filter_layout.addStretch(1)

        self._report_model = ListTableModel(
            (
                ("Order #", lambda row: getattr(row, "order_number", "")),
                ("Customer", lambda row: getattr(row, "customer_name", "")),
                (
                    "Order Date",
                    lambda row: getattr(row, "order_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "order_date", None)
                    else "",
                ),
                (
                    "Ship Date",
                    lambda row: getattr(row, "ship_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "ship_date", None)
                    else "",
                ),
                (
                    "Target Date",
                    lambda row: getattr(row, "target_completion_date", date.min).strftime("%Y-%m-%d")
                    if getattr(row, "target_completion_date", None)
                    else "",
                ),
                ("Status", lambda row: getattr(row, "status", "")),
                ("Carrier", lambda row: getattr(row, "carrier", "")),
                ("Tracking #", lambda row: getattr(row, "tracking_number", "")),
                ("Items", lambda row: getattr(row, "item_count", 0)),
                (
                    "Total (Displayed)",
                    lambda row, mw=self: f"${getattr(row, 'total_amount', 0.0) + (getattr(row, 'tax_amount', 0.0) if getattr(mw._app_settings, 'tax_add_to_total', False) else 0.0):,.2f}",
                ),
                (
                    "Tax",
                    lambda row: f"${getattr(row, 'tax_amount', 0.0):,.2f}",
                ),
                (
                    "Freebie Cost",
                    lambda row: f"${getattr(row, 'freebie_cost', 0):,.2f}",
                ),
                (
                    "Net Revenue",
                    lambda row: f"${getattr(row, 'net_revenue', getattr(row, 'total_amount', 0) - getattr(row, 'freebie_cost', 0)):,.2f}",
                ),
                ("Cost", lambda row: f"${getattr(row, 'total_cost', 0):,.2f}"),
                ("Profit", lambda row: f"${getattr(row, 'profit', 0):,.2f}"),
                (
                    "Margin",
                    lambda row: f"{getattr(row, 'margin', 0) * 100:,.1f}%"
                    if getattr(row, "total_amount", 0)
                    else "--",
                ),
                ("Adjustments", lambda row: getattr(row, "adjustment_summary", "")),
                ("Products", lambda row: getattr(row, "products", "")),
            )
        )
        report_table = QTableView()
        report_table.setModel(self._report_model)
        self._configure_table(report_table)
        layout.addWidget(report_table, stretch=1)

        self._report_summary_label = QLabel()
        self._report_summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._report_summary_label)

        self._report_status_label = QLabel()
        layout.addWidget(self._report_status_label)

    # History tab
    def _build_history_tab(self) -> None:
        layout = QVBoxLayout()
        self._history_tab.setLayout(layout)

        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        self._history_order_filter = QLineEdit()
        self._history_order_filter.setPlaceholderText("Order # contains…")
        filter_layout.addWidget(self._history_order_filter, stretch=2)

        self._history_start_filter = QDateEdit()
        self._history_start_filter.setCalendarPopup(True)
        self._history_start_filter.setSpecialValueText("Start Date")
        self._history_start_filter.setDate(QDate.currentDate())
        filter_layout.addWidget(self._history_start_filter)

        self._history_end_filter = QDateEdit()
        self._history_end_filter.setCalendarPopup(True)
        self._history_end_filter.setSpecialValueText("End Date")
        self._history_end_filter.setDate(QDate.currentDate())
        filter_layout.addWidget(self._history_end_filter)

        apply_button = QPushButton("Apply Filters")
        apply_button.clicked.connect(self._apply_history_filters)
        filter_layout.addWidget(apply_button)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_history_filters)
        filter_layout.addWidget(clear_button)

        def when_text(row: object) -> str:
            value = getattr(row, "created_at", None)
            if not value:
                return ""
            try:
                return value.strftime("%Y-%m-%d %H:%M")
            except AttributeError:
                return str(value)

        self._history_model = ListTableModel(
            (
                ("When", when_text),
                ("Order #", lambda row: getattr(row, "order_number", "")),
                ("Event", lambda row: getattr(row, "event_type", "")),
                ("Description", lambda row: getattr(row, "description", "")),
                (
                    "Amount Δ",
                    lambda row: f"${getattr(row, 'amount_delta', 0):,.2f}",
                ),
            )
        )
        self._history_table = QTableView()
        self._history_table.setModel(self._history_model)
        self._configure_table(self._history_table)
        layout.addWidget(self._history_table, stretch=1)

        self._history_status_label = QLabel()
        layout.addWidget(self._history_status_label)

    def _apply_history_filters(self) -> None:
        self._load_history()

    def _clear_history_filters(self) -> None:
        self._history_order_filter.clear()
        self._history_start_filter.setDate(QDate.currentDate())
        self._history_end_filter.setDate(QDate.currentDate())
        self._load_history()

    def _load_history(self) -> None:
        if not hasattr(self, "_history_model"):
            return

        order_filter = self._history_order_filter.text().strip()
        order_number = order_filter if order_filter else None
        start_date = self._extract_optional_date(self._history_start_filter)
        end_date = self._extract_optional_date(self._history_end_filter)

        events = order_service.list_order_history(
            order_number=order_number,
            start_date=start_date,
            end_date=end_date,
            limit=200,
        )
        self._history_model.update_rows(events)

        if events:
            net_total = sum(getattr(event, "amount_delta", 0.0) for event in events)
            self._history_status_label.setText(
                f"{len(events)} events shown | Net impact: ${net_total:,.2f}"
            )
        else:
            self._history_status_label.setText("No history events match the current filters.")

    def _load_notifications(self) -> None:
        if not hasattr(self, "_notifications_model"):
            return

        notifications = order_service.list_notifications()
        self._notifications_model.update_rows(notifications)

    # Products tab
    def _build_products_tab(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self._products_tab.setLayout(layout)

        intro = QLabel(
            "Manage products in a dedicated workspace while keeping orders focused on fulfillment. "
            "Use the Product Manager to review inventory forecasts, update product details, and keep "
            "alerts current."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        manage_button = QPushButton("Open Product Manager")
        manage_button.setFixedWidth(220)
        manage_button.clicked.connect(self._open_product_manager)
        layout.addWidget(manage_button, alignment=Qt.AlignmentFlag.AlignLeft)

        tips = QLabel(
            "Tip: add quick product placeholders while entering orders. Complete their descriptions, "
            "photos, and statuses later from the Product Manager."
        )
        tips.setWordWrap(True)
        layout.addWidget(tips)

        layout.addStretch(1)

    # Graphs tab
    def _build_graphs_tab(self) -> None:
        layout = QVBoxLayout()
        self._graphs_tab.setLayout(layout)

        self._chart_view = QChartView()
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout.addWidget(self._chart_view, stretch=1)

    # Settings tab
    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout()
        self._settings_tab.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self._business_name_input = QLineEdit(self._app_settings.business_name)
        form_layout.addRow("Business Name", self._business_name_input)

        self._show_business_name_checkbox = QCheckBox("Show business name on dashboard")
        self._show_business_name_checkbox.setChecked(self._app_settings.dashboard_show_business_name)
        form_layout.addRow("Display Title", self._show_business_name_checkbox)

        city_state_container = QWidget()
        city_state_layout = QHBoxLayout()
        city_state_layout.setContentsMargins(0, 0, 0, 0)
        city_state_layout.setSpacing(8)
        city_state_container.setLayout(city_state_layout)

        self._home_city_input = QLineEdit(self._app_settings.dashboard_home_city)
        self._home_city_input.setPlaceholderText("City (e.g., New Albany)")
        city_state_layout.addWidget(self._home_city_input)

        self._home_state_input = QLineEdit(self._app_settings.dashboard_home_state)
        self._home_state_input.setPlaceholderText("State")
        self._home_state_input.setMaxLength(2)
        self._home_state_input.setFixedWidth(70)
        city_state_layout.addWidget(self._home_state_input)
        city_state_layout.addStretch(1)

        form_layout.addRow("Home City/State", city_state_container)

        self._home_state_input.editingFinished.connect(self._normalize_home_state_input)
        self._home_city_input.editingFinished.connect(self._normalize_home_city_input)

        self._tax_rate_input = QDoubleSpinBox()
        self._tax_rate_input.setRange(0.0, 100.0)
        self._tax_rate_input.setDecimals(2)
        self._tax_rate_input.setSingleStep(0.1)
        self._tax_rate_input.setSuffix(" %")
        self._tax_rate_input.setValue(self._app_settings.tax_rate_percent)
        form_layout.addRow("Sales Tax Rate", self._tax_rate_input)

        self._tax_show_invoice_checkbox = QCheckBox("Show tax line on invoices")
        self._tax_show_invoice_checkbox.setChecked(self._app_settings.tax_show_on_invoice)
        form_layout.addRow("Invoice Tax Display", self._tax_show_invoice_checkbox)

        self._tax_include_total_checkbox = QCheckBox("Include tax in totals")
        self._tax_include_total_checkbox.setChecked(self._app_settings.tax_add_to_total)
        form_layout.addRow("Totals Preference", self._tax_include_total_checkbox)

        logo_path_container = QWidget()
        logo_path_layout = QHBoxLayout()
        logo_path_layout.setContentsMargins(0, 0, 0, 0)
        logo_path_layout.setSpacing(6)
        logo_path_container.setLayout(logo_path_layout)

        self._logo_path_input = QLineEdit(self._app_settings.dashboard_logo_path)
        logo_path_layout.addWidget(self._logo_path_input)

        browse_logo_button = QPushButton("Browse…")
        browse_logo_button.clicked.connect(self._handle_browse_logo)
        logo_path_layout.addWidget(browse_logo_button)

        clear_logo_button = QPushButton("Clear")
        clear_logo_button.clicked.connect(self._handle_clear_logo)
        logo_path_layout.addWidget(clear_logo_button)

        form_layout.addRow("Dashboard Logo", logo_path_container)

        self._logo_alignment_combo = QComboBox()
        placements = [
            ("top-left", "Top Left"),
            ("top-center", "Top Center"),
            ("top-right", "Top Right"),
            ("bottom-left", "Bottom Left"),
            ("bottom-center", "Bottom Center"),
            ("bottom-right", "Bottom Right"),
        ]
        for key, label in placements:
            self._logo_alignment_combo.addItem(label, key)
        align_index = self._logo_alignment_combo.findData(self._app_settings.dashboard_logo_alignment)
        if align_index >= 0:
            self._logo_alignment_combo.setCurrentIndex(align_index)
        form_layout.addRow("Logo Placement", self._logo_alignment_combo)

        self._logo_size_input = QSpinBox()
        self._logo_size_input.setRange(24, 1024)
        self._logo_size_input.setSingleStep(8)
        self._logo_size_input.setValue(self._app_settings.dashboard_logo_size)
        form_layout.addRow("Logo Height (px)", self._logo_size_input)

        self._low_inventory_input = QSpinBox()
        self._low_inventory_input.setMinimum(0)
        self._low_inventory_input.setMaximum(10_000)
        self._low_inventory_input.setValue(self._app_settings.low_inventory_threshold)
        form_layout.addRow("Low Inventory Threshold", self._low_inventory_input)

        self._order_number_format_input = QLineEdit(self._app_settings.order_number_format)
        form_layout.addRow("Order # Format", self._order_number_format_input)

        self._order_number_next_input = QSpinBox()
        self._order_number_next_input.setMinimum(1)
        self._order_number_next_input.setMaximum(1_000_000_000)
        self._order_number_next_input.setValue(self._app_settings.order_number_next)
        form_layout.addRow("Next Order #", self._order_number_next_input)

        invoice_button = QPushButton("Open Invoice Manager")
        invoice_button.setFixedWidth(200)
        invoice_button.clicked.connect(self._open_invoice_manager)
        layout.addWidget(invoice_button, alignment=Qt.AlignmentFlag.AlignLeft)

        format_hint = QLabel("Use {seq} as the placeholder, e.g., 'ORD-{seq:04d}'.")
        format_hint.setWordWrap(True)
        format_hint.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(format_hint)
        layout.addSpacing(6)

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self._handle_save_settings)
        layout.addWidget(save_button)

        self._settings_status_label = QLabel()
        layout.addWidget(self._settings_status_label)
        layout.addStretch(1)
    
    def _build_about_tab(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        self._about_tab.setLayout(layout)

        about_browser = QTextBrowser()
        about_browser.setReadOnly(True)
        about_browser.setOpenExternalLinks(True)
        about_browser.setMinimumHeight(520)
        about_browser.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        about_html = (
            f"<h2>{APP_NAME} {APP_VERSION}</h2>"
            "<p>HustleNest keeps your sales pipeline, fulfillment queue, and inventory health in one desktop workspace. "
            "Use the sections below as a quick-start guide for every tab in the application.</p>"
            "<h3>How to Use HustleNest</h3>"
            "<h4>Dashboard</h4>"
            "<p>Monitor headline metrics (total sales, outstanding and completed orders), review low-inventory and overdue alerts, "
            "and launch directly into product management or order editing. Configure the branding banner in Settings to display your business name and logo.</p>"
            "<h4>Orders</h4>"
            "<p>Create new orders, maintain drafts, or edit existing ones. Add products, mark FREEBIE line items, set target completion dates, "
            "and capture shipping details. The Order Items table now refreshes instantly when you pick an existing order, and the widened Recent Orders "
            "list highlights the attached products for quick triage before you begin editing.</p>"
            "<h4>Products</h4>"
            "<p>Open the Product Manager dialog to add new SKUs, adjust inventory, update statuses, or upload supporting details. "
            "Products created on the fly from the Orders tab can be completed here later.</p>"
            "<h4>Reports</h4>"
            "<p>Filter by week, month, year, or custom date ranges to analyze revenue. Export results to CSV for accounting or forecasting, and "
            "review the totals summary (orders, items, sales) to validate performance.</p>"
            "<h4>History</h4>"
            "<p>Audit the chronological event log for order creations, updates, cancellations, inventory adjustments, and other automated actions.</p>"
            "<h4>Graphs</h4>"
            "<p>Visualize the top product performers with an interactive bar chart. Use this tab to identify sales momentum at a glance.</p>"
            "<h4>Map</h4>"
            "<p>Plot shipping destinations extracted from order addresses. This helps you understand regional demand and plan logistics.</p>"
            "<h4>Settings</h4>"
            "<p>Adjust order numbering formats, manage sequence counters, set low-inventory thresholds, and configure dashboard branding (business title, logo, placement, and size).</p>"
            "<h4>About</h4>"
            "<p>Check your current version, follow the latest release notes, and revisit these how-to instructions whenever you need a refresher.</p>"
            "<h3>Highlights</h3>"
            "<ul>"
            "<li>Capture detailed orders with configurable numbering, FREEBIE support, and flexible shipping fields.</li>"
            "<li>Monitor dashboards, low-inventory alerts, and overdue order notifications in one control center.</li>"
            "<li>Review customer history, sales analytics, and exportable reports for bookkeeping.</li>"
            "<li>Forecast inventory needs from recent sales velocity to stay ahead of demand.</li>"
            "</ul>"
            "<h3>Recent Enhancements</h3>"
            "<ul>"
            "<li>Saving an existing order now clears the selection so the form is primed for the next entry without manual resets.</li>"
            "<li>Orders tab inputs call out where to pick products, set quantities, and review pricing with fresh inline labels and tooltips.</li>"
            "<li>Invoice exports drop the starter placeholder comment, ensuring PDFs only include your saved messaging.</li>"
            "</ul>"
            f"<p>Project home: <a href=\"{REPOSITORY_URL}\">{REPOSITORY_URL}</a></p>"
        )
        about_browser.setHtml(about_html)
        layout.addWidget(about_browser)

        self._update_status_label = QLabel("Checking for updates...")
        self._update_status_label.setWordWrap(True)
        self._update_status_label.setTextFormat(Qt.TextFormat.RichText)
        self._update_status_label.setOpenExternalLinks(True)
        layout.addWidget(self._update_status_label)
        layout.addStretch(1)

    def _check_for_updates(self) -> None:
        result = check_for_updates()
        if result.error:
            self._update_status_label.setText(f"Update check failed: {result.error}")
            return

        if result.is_newer and result.latest_version:
            link = result.download_url or RELEASES_URL
            self._update_status_label.setText(
                f'Update available: <a href="{link}">{result.latest_version}</a>. '
                "Visit the releases page to download."
            )
            QMessageBox.information(
                self,
                "Update Available",
                (
                    f"A newer version ({result.latest_version}) is available.\n"
                    f"Visit {link} to download the latest build."
                ),
            )
        else:
            latest = result.latest_version or APP_VERSION
            self._update_status_label.setText(
                f"You are running the latest version ({latest})."
            )

    # Dashboard actions
    def _update_dashboard_branding(self) -> None:
        if not hasattr(self, "_dashboard_brand_widget"):
            return

        name_text = self._app_settings.business_name.strip() or APP_NAME
        show_name = self._app_settings.dashboard_show_business_name and bool(name_text)
        self._business_title_label.setText(name_text)
        self._business_title_label.setVisible(show_name)

        show_logo = False
        self._dashboard_logo_label.clear()
        self._dashboard_logo_label.setToolTip("")

        logo_path_value = self._app_settings.dashboard_logo_path.strip()
        if logo_path_value:
            candidate = Path(logo_path_value).expanduser()
            if candidate.exists():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    target_height = max(24, min(1024, int(self._app_settings.dashboard_logo_size)))
                    scaled = pixmap.scaledToHeight(
                        target_height,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._dashboard_logo_label.setPixmap(scaled)
                    self._dashboard_logo_label.setVisible(True)
                    self._dashboard_logo_label.setToolTip(candidate.name)
                    show_logo = True
                else:
                    self._dashboard_logo_label.setToolTip("Unable to load logo image.")
            else:
                self._dashboard_logo_label.setToolTip("Logo file not found.")

        if not show_logo:
            self._dashboard_logo_label.setPixmap(QPixmap())
            self._dashboard_logo_label.setVisible(False)

        show_brand = show_name or show_logo
        self._dashboard_brand_widget.setVisible(show_brand)

        for layout in (self._dashboard_brand_top_layout, self._dashboard_brand_bottom_layout):
            for index in reversed(range(layout.count())):
                item = layout.takeAt(index)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        if not show_brand:
            self._dashboard_brand_top.setVisible(False)
            self._dashboard_brand_bottom.setVisible(False)
            return

        placement_value = (self._app_settings.dashboard_logo_alignment or "top-left").lower()
        placement_map = {
            "top-left": (self._dashboard_brand_top_layout, Qt.AlignmentFlag.AlignLeft, "top"),
            "top-center": (self._dashboard_brand_top_layout, Qt.AlignmentFlag.AlignHCenter, "top"),
            "top-right": (self._dashboard_brand_top_layout, Qt.AlignmentFlag.AlignRight, "top"),
            "bottom-left": (self._dashboard_brand_bottom_layout, Qt.AlignmentFlag.AlignLeft, "bottom"),
            "bottom-center": (self._dashboard_brand_bottom_layout, Qt.AlignmentFlag.AlignHCenter, "bottom"),
            "bottom-right": (self._dashboard_brand_bottom_layout, Qt.AlignmentFlag.AlignRight, "bottom"),
        }
        target_layout, align_flag, vertical_position = placement_map.get(
            placement_value,
            placement_map["top-left"],
        )

        self._dashboard_brand_layout.setAlignment(align_flag)
        target_layout.addWidget(self._dashboard_brand_widget, 0, align_flag)

        self._dashboard_brand_top.setVisible(vertical_position == "top")
        self._dashboard_brand_bottom.setVisible(vertical_position == "bottom")

    def refresh_dashboard(self) -> None:
        self._update_dashboard_branding()
        snapshot = order_service.get_dashboard_snapshot()
        displayed_sales = snapshot.total_sales + (snapshot.tax_total if getattr(self._app_settings, "tax_add_to_total", False) else 0.0)
        self._total_sales_label.setText(f"Total Sales: ${displayed_sales:,.2f}")
        if getattr(self._app_settings, "tax_add_to_total", False):
            self._total_sales_label.setToolTip("Includes collected tax based on Settings preferences.")
        else:
            self._total_sales_label.setToolTip("Excludes collected tax; see Net Revenue for context.")
        self._net_sales_label.setText(
            f"Net Revenue: ${snapshot.net_sales:,.2f} (Freebies: ${snapshot.freebie_cost:,.2f} | Tax: ${snapshot.tax_total:,.2f})"
        )
        self._net_sales_label.setToolTip("Net revenue remains pre-tax to track true earnings; tax tracked separately.")
        self._outstanding_label.setText(f"Outstanding Orders: {snapshot.outstanding_orders}")
        self._completed_label.setText(f"Completed Orders: {snapshot.completed_orders}")
        self._product_model.update_rows(snapshot.product_breakdown)
        self._customer_model.update_rows(snapshot.top_customers)
        self._outstanding_model.update_rows(snapshot.outstanding_details)
        self._completed_model.update_rows(snapshot.completed_details)
        if self._product_manager_dialog is not None:
            self._product_manager_dialog.refresh_data()
        self._load_notifications()
        self._update_graphs(snapshot.product_breakdown)
        self._load_history()
        self._refresh_map()

    def _load_recent_orders(self, *, select_order_id: Optional[int] = None) -> None:
        orders = order_service.list_recent_orders()
        self._recent_orders_cache = orders
        self._recent_orders_model.update_rows(self._recent_orders_cache)

        target_id: Optional[int] = None
        if select_order_id is not None:
            target_id = int(select_order_id)
        elif self._selected_order is not None and getattr(self._selected_order, "id", None) is not None:
            target_id = int(self._selected_order.id)  # type: ignore[arg-type]

        selected = False
        if target_id is not None:
            for row, order in enumerate(orders):
                order_id_value = getattr(order, "id", None)
                if order_id_value is None:
                    continue
                if int(order_id_value) != target_id:
                    continue

                persisted = order_service.fetch_order(target_id)
                resolved_order = persisted or order
                self._selected_order = resolved_order
                self._editing_order_id = getattr(resolved_order, "id", None)

                if hasattr(self, "_recent_orders_table"):
                    table = self._recent_orders_table
                    selection_model = table.selectionModel()
                    if selection_model is not None:
                        blocker = QSignalBlocker(selection_model)
                        table.selectRow(row)
                        del blocker
                    else:
                        table.selectRow(row)
                    table.scrollTo(table.model().index(row, 0))

                self._load_order_into_form(resolved_order)
                selected = True
                break

        if not selected and select_order_id is None:
            if hasattr(self, "_recent_orders_table"):
                self._start_new_order(clear_status=False)
            else:
                self._selected_order = None
                self._editing_order_id = None

        self._update_order_action_buttons()

    def _handle_new_order(self) -> None:
        self._start_new_order()

    def _start_new_order(self, *, clear_status: bool = True) -> None:
        self._editing_order_id = None
        self._selected_order = None

        if hasattr(self, "_recent_orders_table"):
            selection_model = self._recent_orders_table.selectionModel()
            if selection_model is not None:
                blocker = QSignalBlocker(selection_model)
                selection_model.clearSelection()

        self._pending_items.clear()
        if hasattr(self, "_pending_items_model"):
            self._pending_items_model.clear()

        if hasattr(self, "_pending_items_table"):
            self._pending_items_table.clearSelection()

        self._clear_order_form()
        self._set_item_editing_mode(None)
        self._clear_line_item_inputs()
        self._update_item_action_buttons()

        if clear_status and hasattr(self, "_order_status_label"):
            self._order_status_label.setStyleSheet("")
            self._order_status_label.clear()

    def _format_order_items_brief(self, order: object) -> str:
        items = getattr(order, "items", None)
        if not items:
            return ""

        parts: List[str] = []
        for item in items:
            quantity_raw = getattr(item, "quantity", 0)
            try:
                quantity = int(quantity_raw)
            except (TypeError, ValueError):
                quantity = 0

            name = (getattr(item, "product_name", "") or "").strip()
            if not name:
                name = (getattr(item, "product_sku", "") or "").strip()

            if not name and quantity <= 0:
                continue

            label = name if name else "Item"
            if quantity > 0:
                parts.append(f"{quantity} x {label}")
            else:
                parts.append(label)

        summary = ", ".join(parts)
        if len(summary) > 120:
            summary = summary[:117] + "..."
        return summary

    def _load_order_into_form(self, order: Order) -> None:
        self._editing_order_id = getattr(order, "id", None)
        self._order_number_input.setText(order.order_number)
        self._customer_name_input.setText(order.customer_name)
        self._customer_address_input.setPlainText(order.customer_address)

        self._order_date_input.setDate(QDate(order.order_date.year, order.order_date.month, order.order_date.day))

        self._ship_date_input.blockSignals(True)
        if order.ship_date is not None:
            self._ship_date_input.setDate(QDate(order.ship_date.year, order.ship_date.month, order.ship_date.day))
        else:
            self._ship_date_input.setDate(QDate.currentDate())
        self._ship_date_input.blockSignals(False)

        self._target_completion_input.blockSignals(True)
        if order.target_completion_date is not None:
            target = order.target_completion_date
            self._target_completion_input.setDate(QDate(target.year, target.month, target.day))
        else:
            self._target_completion_input.setDate(QDate.currentDate())
        self._target_completion_input.blockSignals(False)

        status_index = self._status_input.findText(
            order.status,
            Qt.MatchFlag.MatchFixedString,
        )
        if status_index >= 0:
            self._status_input.setCurrentIndex(status_index)
        else:
            self._status_input.setCurrentText(order.status)

        self._set_paid_checkbox(order.is_paid)

        self._carrier_input.setText(order.carrier)
        self._tracking_input.setText(order.tracking_number)
        if hasattr(self, "_order_notes_input"):
            self._order_notes_input.setPlainText(order.notes or "")

        self._pending_items = [replace(item, cost_components=self._copy_components(item.cost_components)) for item in order.items]
        self._pending_items_model.update_rows(self._pending_items)
        if hasattr(self, "_pending_items_table"):
            self._pending_items_table.clearSelection()

        self._set_item_editing_mode(None)
        self._clear_line_item_inputs()
        self._update_item_action_buttons()

        self._order_status_label.setStyleSheet("color: #1976d2;")
        self._order_status_label.setText("Editing existing order. Save to apply changes.")
        self._update_cost_summary()

    def _run_report(self) -> None:
        start_date = self._extract_optional_date(self._report_start_date)
        end_date = self._extract_optional_date(self._report_end_date)

        rows = order_service.list_order_report(start_date, end_date)
        self._current_report_rows = list(rows)
        self._report_model.update_rows(self._current_report_rows)
        self._reports_header_label.setText(f"{self._app_settings.business_name} Reports")

        if hasattr(self, "_report_export_button"):
            self._report_export_button.setEnabled(bool(self._current_report_rows))

        order_count = len(self._current_report_rows)
        total_sales = sum(getattr(row, "total_amount", 0.0) for row in self._current_report_rows)
        total_cost = sum(getattr(row, "total_cost", 0.0) for row in self._current_report_rows)
        total_profit = sum(getattr(row, "profit", 0.0) for row in self._current_report_rows)
        freebie_total = sum(getattr(row, "freebie_cost", 0.0) for row in self._current_report_rows)
        tax_total = sum(getattr(row, "tax_amount", 0.0) for row in self._current_report_rows)
        net_sales = total_sales - freebie_total
        if net_sales > 0:
            overall_margin = total_profit / net_sales
        elif total_sales > 0:
            overall_margin = total_profit / total_sales
        else:
            overall_margin = 0.0
        total_items = sum(getattr(row, "item_count", 0) for row in self._current_report_rows)
        displayed_sales = total_sales + (tax_total if getattr(self._app_settings, "tax_add_to_total", False) else 0.0)
        summary_text = (
            f"Orders: {order_count} | Items: {total_items} | Sales: ${total_sales:,.2f} | "
            f"Tax: ${tax_total:,.2f} | Displayed Sales: ${displayed_sales:,.2f} | "
            f"Freebie Cost: ${freebie_total:,.2f} | Net Revenue: ${net_sales:,.2f} | "
            f"Cost: ${total_cost:,.2f} | Profit: ${total_profit:,.2f} | Margin: {overall_margin * 100:,.1f}%"
        )
        if hasattr(self, "_report_summary_label"):
            self._report_summary_label.setText(summary_text)

        if not self._current_report_rows:
            self._report_status_label.setText("No orders found for the selected range.")
            self._report_status_label.setStyleSheet("")
        else:
            self._report_status_label.setText(f"{len(self._current_report_rows)} orders found.")
            self._report_status_label.setStyleSheet("")

    def _handle_export_report(self) -> None:
        if not self._current_report_rows:
            self._show_message("Run a report before exporting.")
            return

        default_name = f"{self._app_settings.business_name} Report.csv".replace(" ", "_")
        suggested_path = str(Path.home() / default_name)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            suggested_path,
            "CSV Files (*.csv)"
        )

        if not filename:
            return

        try:
            exported_path = order_service.export_order_report(self._current_report_rows, filename)
        except Exception as exc:  # noqa: BLE001
            self._report_status_label.setStyleSheet("color: #d32f2f;")
            self._report_status_label.setText(f"Export failed: {exc}")
            return

        self._report_status_label.setStyleSheet("color: #2e7d32;")
        self._report_status_label.setText(f"Report exported to {exported_path}")

    def _refresh_products(self, *, select_sku: Optional[str] = None) -> None:
        target_sku = select_sku
        if target_sku is None:
            current_data = self._product_combo.currentData()
            if isinstance(current_data, Product):
                target_sku = current_data.sku

        self._products_cache = order_service.list_products()
        self._update_product_combo(select_sku=target_sku)

        if self._product_manager_dialog is not None:
            self._product_manager_dialog.refresh_data(select_sku=target_sku)

        self._load_notifications()

    def _open_product_manager(self) -> None:
        if self._product_manager_dialog is None:
            dialog = ProductManagerDialog(
                parent=self,
                app_settings=self._app_settings,
                product_status_options=list(self._product_status_options),
                on_products_changed=self._handle_products_changed,
            )
            dialog.destroyed.connect(self._on_product_manager_destroyed)
            self._product_manager_dialog = dialog
        else:
            self._product_manager_dialog.update_app_settings(self._app_settings)

        dialog = self._product_manager_dialog
        if dialog is None:
            return

        current_data = self._product_combo.currentData()
        selected_sku = current_data.sku if isinstance(current_data, Product) else None
        dialog.refresh_data(select_sku=selected_sku)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _handle_products_changed(self, select_sku: Optional[str]) -> None:
        self._refresh_products(select_sku=select_sku)
        self.refresh_dashboard()

    def _on_product_manager_destroyed(self, _obj: Optional[object] = None) -> None:
        self._product_manager_dialog = None

    def _update_product_combo(self, *, select_sku: Optional[str] = None) -> None:
        current_text = self._product_combo.currentText()

        self._product_combo.blockSignals(True)
        self._product_combo.clear()

        for product in self._products_cache:
            label = f"{product.sku} - {product.name}"
            self._product_combo.addItem(label, product)

        if select_sku:
            index = next((i for i, product in enumerate(self._products_cache) if product.sku == select_sku), -1)
            if index >= 0:
                self._product_combo.setCurrentIndex(index)
        else:
            self._product_combo.setCurrentText(current_text)

        self._product_combo.blockSignals(False)

    def _refresh_map(self) -> None:
        if not hasattr(self, "_map_view"):
            return

        show_lines = True
        line_style = "curved"
        line_color = "#3f51b5"
        line_pattern = "solid"
        base_layer = "light"
        shade_states = False
        territories: List[Dict[str, Any]] = []

        if hasattr(self, "_map_lines_checkbox"):
            show_lines = self._map_lines_checkbox.isChecked()
        if hasattr(self, "_map_line_style") and self._map_line_style.currentData() is not None:
            line_style = str(self._map_line_style.currentData())
        if hasattr(self, "_map_line_color") and self._map_line_color.currentData() is not None:
            line_color = str(self._map_line_color.currentData())
        if hasattr(self, "_map_line_pattern") and self._map_line_pattern.currentData() is not None:
            line_pattern = str(self._map_line_pattern.currentData())
        if hasattr(self, "_map_base_layer_combo") and self._map_base_layer_combo.currentData() is not None:
            layer_candidate = str(self._map_base_layer_combo.currentData())
            if layer_candidate in {"light", "dark"}:
                base_layer = layer_candidate
        if hasattr(self, "_map_territory_checkbox"):
            shade_states = self._map_territory_checkbox.isChecked()

        try:
            destinations = order_service.list_order_destinations()
        except Exception as exc:  # noqa: BLE001
            self._map_status_label.setStyleSheet("color: #d32f2f;")
            self._map_status_label.setText(f"Unable to load destinations: {exc}")
            self._map_view.setHtml(self._build_placeholder_map_html("Map data unavailable."))
            return

        home_location: Optional[Dict[str, Any]] = None
        home_error: Optional[str] = None
        home_city = (self._app_settings.dashboard_home_city or "").strip()
        home_state = (self._app_settings.dashboard_home_state or "").strip().upper()
        if home_city and home_state:
            home_coords = self._geocode_home_location(home_city, home_state)
            if home_coords is None:
                home_error = f"Home location '{home_city}, {home_state}' could not be located."
            else:
                lat, lon = home_coords
                home_location = {
                    "lat": lat,
                    "lon": lon,
                    "label": f"Home Base ({home_city}, {home_state})",
                }
        elif home_city or home_state:
            home_error = "Provide both city and state to plot your home base."

        markers: List[Dict[str, Any]] = []

        if shade_states:
            territory_totals: Dict[str, int] = {}
            for destination in destinations:
                state_code = (destination.state or "").strip().upper()
                if state_code not in STATE_CODE_TO_NAME:
                    continue
                territory_totals[state_code] = territory_totals.get(state_code, 0) + int(destination.count)
            territories = [
                {"code": code, "name": STATE_CODE_TO_NAME.get(code, code), "count": count}
                for code, count in sorted(territory_totals.items(), key=lambda item: item[1], reverse=True)
            ]

        for destination in destinations[:75]:
            coordinates = self._geocode_destination(destination.city, destination.state)
            if coordinates is None:
                continue
            lat, lon = coordinates
            orders_preview = destination.order_numbers[:10]
            markers.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "label": f"{destination.city}, {destination.state}",
                    "count": destination.count,
                    "orders": orders_preview,
                }
            )

        if not markers and home_location is None:
            status_style = "color: #d32f2f;" if destinations else ""
            status_message = (
                "No coordinates available for the current destinations."
                if destinations
                else "No destinations available yet."
            )
            if home_error:
                status_message = f"{status_message} {home_error}"
                status_style = "color: #ef6c00;"
            self._map_status_label.setStyleSheet(status_style)
            self._map_status_label.setText(status_message)
            self._map_view.setHtml(self._build_placeholder_map_html("No mappable destinations found."))
            return

        status_parts: List[str] = []
        if markers:
            status_parts.append(f"Showing {len(markers)} destination(s).")
        else:
            status_parts.append(
                "No coordinates available for the current destinations." if destinations else "No destinations yet."
            )
        if home_location is not None:
            status_parts.append(f"Home base: {home_city}, {home_state}.")
        elif not home_error and not home_city and not home_state:
            status_parts.append("Set your home city and state in Settings to add a home base.")
        if home_error:
            status_parts.append(home_error)
        if shade_states:
            if territories:
                status_parts.append(f"States shaded: {len(territories)}.")
            else:
                status_parts.append("Shade option on, but no US state data yet.")

        status_style = "color: #ef6c00;" if home_error else ""
        self._map_status_label.setStyleSheet(status_style)
        self._map_status_label.setText(" ".join(status_parts))
        self._map_view.setHtml(
            self._build_map_html(
                markers,
                home_location,
                show_lines=show_lines,
                line_style=line_style,
                line_color=line_color,
                line_pattern=line_pattern,
                base_layer=base_layer,
                shade_states=shade_states,
                territories=territories,
            )
        )

    def _geocode_location(self, cache_key: str, query: str) -> Optional[Tuple[float, float]]:
        normalized_key = cache_key.strip().lower()
        cached = self._geocode_cache.get(normalized_key)
        if cached is not None:
            return cached

        url = f"https://nominatim.openstreetmap.org/search?{urlencode({'format': 'json', 'limit': 1, 'q': query})}"
        request = Request(url, headers={"User-Agent": "HustleNestApp/1.0 (support@hustlenest.local)"})

        try:
            with urlopen(request, timeout=8) as response:
                payload = response.read()
        except (HTTPError, URLError, TimeoutError):
            return None

        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if not data:
            return None

        try:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
        except (KeyError, ValueError, TypeError):
            return None

        coordinates = (lat, lon)
        self._geocode_cache[normalized_key] = coordinates
        return coordinates

    def _geocode_destination(self, city: str, state: str) -> Optional[Tuple[float, float]]:
        query = f"{city}, {state}, USA"
        return self._geocode_location(f"{city}, {state}", query)

    def _geocode_home_location(self, city: str, state: str) -> Optional[Tuple[float, float]]:
        if not city or not state:
            return None
        cache_key = f"home:{city},{state}"
        query = f"{city}, {state}, USA"
        return self._geocode_location(cache_key, query)

    @staticmethod
    def _build_map_html(
        markers: List[Dict[str, Any]],
        home_location: Optional[Dict[str, Any]],
        *,
        show_lines: bool = True,
        line_style: str = "curved",
        line_color: str = "#3f51b5",
        line_pattern: str = "solid",
        base_layer: str = "light",
        shade_states: bool = False,
        territories: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        valid_styles = {"curved", "straight"}
        valid_patterns = {"solid", "dashed"}
        valid_layers = {"light", "dark"}
        style_value = line_style if line_style in valid_styles else "curved"
        pattern_value = line_pattern if line_pattern in valid_patterns else "solid"
        color_value = line_color.strip() if isinstance(line_color, str) and line_color.strip() else "#3f51b5"
        layer_value = base_layer if base_layer in valid_layers else "light"
        territory_payload = territories or []
        shade_payload = bool(shade_states) and bool(territory_payload)

        config_payload = {
            "showLines": bool(show_lines),
            "lineStyle": style_value,
            "lineColor": color_value,
            "linePattern": pattern_value,
            "baseLayer": layer_value,
            "shadeTerritories": shade_payload,
            "territories": territory_payload,
        }

        markers_json = json.dumps(markers)
        home_json = json.dumps(home_location) if home_location else "null"
        config_json = json.dumps(config_payload)
        geojson_url = json.dumps(US_STATES_GEOJSON_URL)

        return (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset=\"utf-8\"/>"
            "<title>Order Destinations</title>"
            "<link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\"/>"
            "<style>html, body, #map { height: 100%; margin: 0; }</style>"
            "</head><body><div id=\"map\"></div>"
            "<script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>"
            "<script>"
            f"const markers = {markers_json};"
            f"const homeLocation = {home_json};"
            f"const config = {config_json};"
            f"const geojsonSource = {geojson_url};"
            "const map = L.map('map');"
            "const tileSources = {"
            "    light: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {"
            "        maxZoom: 18,"
            "        attribution: '&copy; OpenStreetMap contributors'"
            "    }),"
            "    dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {"
            "        maxZoom: 18,"
            "        attribution: '&copy; OpenStreetMap contributors &copy; CARTO'"
            "    })"
            "};"
            "const selectedLayer = tileSources[config.baseLayer] || tileSources.light;"
            "selectedLayer.addTo(map);"
            "const bounds = [];"
            "markers.forEach((item) => {"
            "    const details = [];"
            "    details.push('<strong>' + item.label + '</strong>');"
            "    details.push(item.count + (item.count === 1 ? ' order' : ' orders'));"
            "    if (item.orders && item.orders.length) {"
            "        details.push('Orders: ' + item.orders.join(', '));"
            "    }"
            "    L.marker([item.lat, item.lon]).addTo(map).bindPopup(details.join('<br/>'));"
            "    bounds.push([item.lat, item.lon]);"
            "});"
            "if (homeLocation) {"
            "    const baseMarker = L.circleMarker([homeLocation.lat, homeLocation.lon], {"
            "        radius: 8,"
            "        color: '#d32f2f',"
            "        weight: 2,"
            "        fillColor: '#ff7043',"
            "        fillOpacity: 0.9"
            "    }).addTo(map);"
            "    baseMarker.bindPopup(homeLocation.label || 'Home Base');"
            "    bounds.push([homeLocation.lat, homeLocation.lon]);"
            "}"
            "function buildArcPoints(start, end, offsetIndex) {"
            "    const [lat1, lon1] = start;"
            "    const [lat2, lon2] = end;"
            "    const dx = lat2 - lat1;"
            "    const dy = lon2 - lon1;"
            "    const distance = Math.sqrt(dx * dx + dy * dy) || 1;"
            "    const direction = offsetIndex % 2 === 0 ? 1 : -1;"
            "    const curvature = 0.35 + Math.min(distance, 1.2) * 0.1;"
            "    const midLat = (lat1 + lat2) / 2;"
            "    const midLon = (lon1 + lon2) / 2;"
            "    const perpLat = (-dy / distance) * curvature * direction;"
            "    const perpLon = (dx / distance) * curvature * direction;"
            "    const controlLat = midLat + perpLat;"
            "    const controlLon = midLon + perpLon;"
            "    const points = [];"
            "    const steps = 24;"
            "    for (let step = 0; step <= steps; step += 1) {"
            "        const t = step / steps;"
            "        const oneMinusT = 1 - t;"
            "        const lat = oneMinusT * oneMinusT * lat1 + 2 * oneMinusT * t * controlLat + t * t * lat2;"
            "        const lon = oneMinusT * oneMinusT * lon1 + 2 * oneMinusT * t * controlLon + t * t * lon2;"
            "        points.push([lat, lon]);"
            "    }"
            "    return points;"
            "}"
            "if (config.showLines && homeLocation && markers.length) {"
            "    const origin = [homeLocation.lat, homeLocation.lon];"
            "    markers.forEach((item, index) => {"
            "        let segments;"
            "        if (config.lineStyle === 'straight') {"
            "            segments = [origin, [item.lat, item.lon]];"
            "        } else {"
            "            segments = buildArcPoints(origin, [item.lat, item.lon], index);"
            "        }"
            "        const options = { color: config.lineColor || '#3f51b5', weight: 2, opacity: 0.7 };"
            "        if (config.linePattern === 'dashed') {"
            "            options.dashArray = '8 6';"
            "        }"
            "        L.polyline(segments, options).addTo(map);"
            "    });"
            "}"
            "if (config.shadeTerritories && config.territories && config.territories.length) {"
            "    const territoryData = config.territories;"
            "    const territoryLookup = new Map();"
            "    let maxCount = 0;"
            "    territoryData.forEach((item) => {"
            "        if (!item) { return; }"
            "        const code = (item.code || '').toString().toUpperCase();"
            "        const name = (item.name || '').toString().toUpperCase();"
            "        const count = Number(item.count) || 0;"
            "        if (code) { territoryLookup.set(code, { name: item.name, count }); }"
            "        if (name) { territoryLookup.set(name, { name: item.name, count }); }"
            "        if (count > maxCount) { maxCount = count; }"
            "    });"
            "    function getFillColor(value) {"
            "        if (!maxCount || !value) { return '#f5f5f5'; }"
            "        const ratio = value / maxCount;"
            "        if (ratio > 0.85) { return '#1b5e20'; }"
            "        if (ratio > 0.65) { return '#2e7d32'; }"
            "        if (ratio > 0.45) { return '#388e3c'; }"
            "        if (ratio > 0.25) { return '#66bb6a'; }"
            "        return '#a5d6a7';"
            "    }"
            "    fetch(geojsonSource)"
            "        .then((response) => response.json())"
            "        .then((geojson) => {"
            "            L.geoJSON(geojson, {"
            "                style: (feature) => {"
            "                    const props = feature && feature.properties ? feature.properties : {};"
            "                    const code = (props.STATE || props.STATE_ABBR || props.state || '').toString().toUpperCase();"
            "                    const name = (props.NAME || props.name || '').toString().toUpperCase();"
                "                    const info = territoryLookup.get(code) || territoryLookup.get(name);"
                "                    const count = info && info.count ? info.count : 0;"
                "                    return {"
                "                        color: '#616161',"
                "                        weight: 1,"
                "                        fillOpacity: count ? 0.7 : 0.1,"
                "                        fillColor: getFillColor(count)"
                "                    };"
                "                },"
                "                onEachFeature: (feature, layer) => {"
                "                    const props = feature && feature.properties ? feature.properties : {};"
                "                    const code = (props.STATE || props.STATE_ABBR || props.state || '').toString().toUpperCase();"
                "                    const nameValue = props.NAME || props.name || 'Unknown';"
                "                    const lookupKey = code || nameValue.toString().toUpperCase();"
                "                    const info = territoryLookup.get(lookupKey);"
                "                    const displayName = info && info.name ? info.name : nameValue;"
                "                    const count = info && info.count ? info.count : 0;"
                "                    const tooltip = `${displayName}<br/>Orders: ${count}`;"
                "                    layer.bindTooltip(tooltip, { sticky: true });"
                "                }"
                "            }).addTo(map);"
                "        })"
                "        .catch(() => {});"
                "}"
            "if (bounds.length === 1) {"
            "    map.setView(bounds[0], 8);"
            "} else if (bounds.length > 1) {"
            "    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });"
            "} else {"
            "    map.setView([37.8, -96.9], 4);"
            "}"
            "</script></body></html>"
        )

    @staticmethod
    def _build_placeholder_map_html(message: str) -> str:
        safe_message = message.replace("<", "&lt;").replace(">", "&gt;")
        return (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset=\"utf-8\"/>"
            "<style>html, body { height: 100%; margin: 0; font-family: Arial, sans-serif; }"
            " .placeholder { display: flex; align-items: center; justify-content: center; height: 100%; color: #555; }"
            "</style></head><body>"
            f"<div class=\"placeholder\">{safe_message}</div>"
            "</body></html>"
        )

    # Orders actions
    def _handle_add_item(self) -> None:
        editing_index = self._editing_line_index
        product = self._resolve_selected_product()
        if product is None:
            return

        was_edit = editing_index is not None and 0 <= editing_index < len(self._pending_items)

        description = self._product_description_input.text().strip()
        quantity = self._quantity_input.value()
        unit_price = self._unit_price_input.value()
        price_mode = self._line_price_type.currentText().strip().upper() if hasattr(self, "_line_price_type") else "STANDARD"
        is_freebie = price_mode == "FREEBIE"

        if unit_price < 0:
            self._show_message("Unit price cannot be negative.")
            return

        if quantity <= 0:
            self._show_message("Quantity must be greater than zero.")
            return

        if unit_price == 0 and not is_freebie:
            self._show_message("Set price above $0.00 or choose the FREEBIE option.")
            return

        if is_freebie:
            unit_price = 0.0
            if not description:
                description = "FREEBIE"

        base_cost = self._base_cost_input.value()
        components = self._copy_components(self._current_cost_components)

        item = OrderItem(
            product_name=product.name,
            product_description=description,
            quantity=quantity,
            unit_price=unit_price,
            product_sku=product.sku,
            product_id=product.id,
            base_unit_cost=base_cost,
            cost_components=components,
            is_freebie=is_freebie,
        )
        if was_edit:
            edit_row = cast(int, editing_index)
            self._pending_items[edit_row] = item
            self._pending_items_model.update_rows(self._pending_items)
            target_row = edit_row
        else:
            self._pending_items.append(item)
            self._pending_items_model.update_rows(self._pending_items)
            target_row = len(self._pending_items) - 1

        self._set_item_editing_mode(None)
        self._clear_line_item_inputs()
        if hasattr(self, "_pending_items_table") and 0 <= target_row < len(self._pending_items):
            self._pending_items_table.selectRow(target_row)
            model_index = self._pending_items_model.index(target_row, 0)
            self._pending_items_table.scrollTo(model_index)
        self._update_item_action_buttons()
        self._set_order_status("Line item updated." if was_edit else "Item added to order.")

    def _on_product_combo_index_changed(self, index: int) -> None:
        if index < 0:
            return
        data = self._product_combo.itemData(index)
        if not isinstance(data, Product):
            return

        if hasattr(self, "_base_cost_input"):
            self._base_cost_input.blockSignals(True)
            self._base_cost_input.setValue(data.base_unit_cost)
            self._base_cost_input.blockSignals(False)

        if hasattr(self, "_unit_price_input") and data.default_unit_price > 0:
            self._unit_price_input.blockSignals(True)
            self._unit_price_input.setValue(data.default_unit_price)
            self._unit_price_input.blockSignals(False)

        self._current_cost_components = self._copy_components(data.pricing_components)
        self._update_cost_summary()

        if data.description and not self._product_description_input.text().strip():
            self._product_description_input.setText(data.description)

    def _resolve_selected_product(self) -> Optional[Product]:
        index = self._product_combo.currentIndex()
        if index >= 0:
            data = self._product_combo.itemData(index)
            if isinstance(data, Product):
                return data

        typed_name = self._product_combo.currentText().strip()
        if not typed_name:
            self._show_message("Select or enter a product before adding an item.")
            return None

        dialog = NewProductDialog(suggested_name=typed_name, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        try:
            product = order_service.ensure_product_exists(dialog.sku, dialog.name)
        except ValueError as exc:  # noqa: BLE001
            self._show_message(str(exc))
            return None

        self._refresh_products(select_sku=product.sku)
        self._show_message(
            "New product added. Open the Product Manager to complete its details.",
        )
        return product

    def _handle_remove_item(self) -> None:
        index = self._pending_items_table.currentIndex()
        if not index.isValid():
            return
        row = index.row()

        if self._editing_line_index is not None:
            if self._editing_line_index == row:
                self._set_item_editing_mode(None)
                self._clear_line_item_inputs()
            elif self._editing_line_index > row:
                self._editing_line_index -= 1

        del self._pending_items[row]
        self._pending_items_model.update_rows(self._pending_items)
        total_rows = len(self._pending_items)
        if total_rows and hasattr(self, "_pending_items_table"):
            next_row = min(row, total_rows - 1)
            self._pending_items_table.selectRow(next_row)
            model_index = self._pending_items_model.index(next_row, 0)
            self._pending_items_table.scrollTo(model_index)
        self._update_item_action_buttons()
        self._set_order_status("Line item removed.")

    def _on_unit_price_changed(self, value: float) -> None:
        if not hasattr(self, "_line_price_type"):
            return

        is_zero = abs(float(value)) < 0.005
        target_text = "FREEBIE" if is_zero else "Standard"

        if self._line_price_type.currentText().lower() == target_text.lower():
            self._refresh_margin_preview()
            return

        self._line_price_type.blockSignals(True)
        self._line_price_type.setCurrentText(target_text)
        self._line_price_type.blockSignals(False)
        self._refresh_margin_preview()

    def _on_price_type_changed(self, text: str) -> None:
        normalized = text.strip().upper()
        if normalized == "FREEBIE":
            if abs(self._unit_price_input.value()) > 0.005:
                self._unit_price_input.blockSignals(True)
                self._unit_price_input.setValue(0.00)
                self._unit_price_input.blockSignals(False)
        else:
            if abs(self._unit_price_input.value()) < 0.005:
                # leave the value at zero but nudge focus so user can enter price
                self._unit_price_input.selectAll()
        self._refresh_margin_preview()

    def _open_cost_component_editor(self) -> None:
        dialog = CostComponentEditorDialog(components=self._current_cost_components, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._current_cost_components = dialog.components()
        self._update_cost_summary()

    def _update_cost_summary(self) -> None:
        if not hasattr(self, "_cost_summary_label"):
            return

        extras_total = sum(component.amount for component in self._current_cost_components)
        extras_count = len(self._current_cost_components)
        self._cost_summary_label.setText(f"Extras: {extras_count} | ${extras_total:,.2f}")
        self._refresh_margin_preview()

    def _refresh_margin_preview(self) -> None:
        if not hasattr(self, "_margin_preview_label"):
            return

        base_cost = self._base_cost_input.value() if hasattr(self, "_base_cost_input") else 0.0
        extras_total = sum(component.amount for component in self._current_cost_components)
        unit_cost = base_cost + extras_total
        unit_price = self._unit_price_input.value() if hasattr(self, "_unit_price_input") else 0.0
        unit_profit = unit_price - unit_cost
        quantity = self._quantity_input.value() if hasattr(self, "_quantity_input") else 0
        line_profit = unit_profit * max(1, quantity)

        if unit_price > 0:
            margin_pct = (unit_profit / unit_price) * 100
            margin_text = f"{margin_pct:.1f}%"
        else:
            margin_text = "--"

        self._margin_preview_label.setText(
            f"Unit Cost: ${unit_cost:,.2f} | Profit/unit: ${unit_profit:,.2f} | "
            f"Line Profit: ${line_profit:,.2f} | Margin: {margin_text}"
        )

    @staticmethod
    def _copy_components(components: Iterable[CostComponent]) -> List[CostComponent]:
        if components is None:
            return []
        return [CostComponent(label=component.label, amount=component.amount) for component in components]

    def _set_item_editing_mode(self, index: Optional[int]) -> None:
        valid_index: Optional[int] = None
        if index is not None and 0 <= index < len(self._pending_items):
            valid_index = index

        self._editing_line_index = valid_index

        if hasattr(self, "_add_item_button"):
            self._add_item_button.setText("Apply Changes" if valid_index is not None else "Add Item")

        if hasattr(self, "_cancel_edit_item_button"):
            self._cancel_edit_item_button.setVisible(valid_index is not None)
            self._cancel_edit_item_button.setEnabled(valid_index is not None)

        self._update_item_action_buttons()

    def _update_item_action_buttons(self) -> None:
        has_selection = False
        if hasattr(self, "_pending_items_table"):
            selection_model = self._pending_items_table.selectionModel()
            if selection_model is not None:
                has_selection = bool(selection_model.selectedRows())

        if hasattr(self, "_edit_item_button"):
            self._edit_item_button.setEnabled(has_selection)
        if hasattr(self, "_remove_item_button"):
            self._remove_item_button.setEnabled(has_selection)

    def _on_pending_items_selection_changed(self, *_args) -> None:
        self._update_item_action_buttons()

    def _handle_edit_item(self) -> None:
        if not self._pending_items:
            return
        if not hasattr(self, "_pending_items_table"):
            return
        selection_model = self._pending_items_table.selectionModel()
        if selection_model is None:
            return
        indexes = selection_model.selectedRows()
        if not indexes:
            self._set_order_status("Select an item before editing.", error=True)
            return
        row = indexes[0].row()
        if not (0 <= row < len(self._pending_items)):
            return
        self._populate_item_editor(row, self._pending_items[row])
        self._set_order_status("Editing selected line item. Apply changes or cancel.")

    def _populate_item_editor(self, index: int, item: OrderItem) -> None:
        self._set_item_editing_mode(index)
        if hasattr(self, "_pending_items_table"):
            self._pending_items_table.selectRow(index)
            model_index = self._pending_items_model.index(index, 0)
            self._pending_items_table.scrollTo(model_index)
        if hasattr(self, "_product_combo"):
            blocker = QSignalBlocker(self._product_combo)
            products = list(getattr(self, "_products_cache", []))
            product_index = next(
                (i for i, product in enumerate(products) if getattr(product, "sku", None) == getattr(item, "product_sku", None)),
                -1,
            )
            if product_index >= 0:
                self._product_combo.setCurrentIndex(product_index)
            else:
                label = (getattr(item, "product_name", None) or getattr(item, "product_sku", None) or "").strip()
                self._product_combo.setCurrentIndex(-1)
                self._product_combo.setCurrentText(label)
            del blocker

        if hasattr(self, "_product_description_input"):
            self._product_description_input.setText(getattr(item, "product_description", ""))
        if hasattr(self, "_quantity_input"):
            self._quantity_input.setValue(int(getattr(item, "quantity", 0) or 0))
        if hasattr(self, "_base_cost_input"):
            blocker = QSignalBlocker(self._base_cost_input)
            self._base_cost_input.setValue(float(getattr(item, "base_unit_cost", 0.0) or 0.0))
            del blocker
        if hasattr(self, "_unit_price_input"):
            blocker = QSignalBlocker(self._unit_price_input)
            self._unit_price_input.setValue(float(getattr(item, "unit_price", 0.0) or 0.0))
            del blocker
        if hasattr(self, "_line_price_type"):
            blocker = QSignalBlocker(self._line_price_type)
            self._line_price_type.setCurrentText("FREEBIE" if getattr(item, "is_freebie", False) else "Standard")
            del blocker

        self._current_cost_components = self._copy_components(item.cost_components)
        self._update_cost_summary()

    def _handle_cancel_item_edit(self) -> None:
        if self._editing_line_index is None:
            return
        self._set_item_editing_mode(None)
        self._clear_line_item_inputs()
        self._set_order_status("Line item edit cancelled.")

    def _handle_save_order(self) -> None:
        customer_name = self._customer_name_input.text().strip()
        customer_address = self._customer_address_input.toPlainText().strip()

        if not customer_name or not customer_address:
            self._set_order_status("Customer name and address are required.", error=True)
            return

        if not self._pending_items:
            self._set_order_status("Add at least one product item before saving.", error=True)
            return

        order_number = self._order_number_input.text().strip()
        status = self._status_input.currentText()
        carrier = self._carrier_input.text().strip()
        tracking_number = self._tracking_input.text().strip()
        notes = self._order_notes_input.toPlainText().strip() if hasattr(self, "_order_notes_input") else ""
        order_date = self._extract_optional_date(self._order_date_input) or date.today()
        ship_date = self._extract_optional_date(self._ship_date_input)
        target_completion = self._extract_optional_date(self._target_completion_input)

        if target_completion and target_completion < order_date:
            self._set_order_status("Target completion date cannot be before the order date.", error=True)
            return

        editing_order_id = self._editing_order_id
        saved_order_id: Optional[int] = None

        try:
            order = order_service.build_order(
                order_number=order_number,
                customer_name=customer_name,
                customer_address=customer_address,
                status=status,
                carrier=carrier,
                tracking_number=tracking_number,
                order_date=order_date,
                ship_date=ship_date,
                target_completion_date=target_completion,
                items=list(self._pending_items),
                is_paid=self._paid_checkbox.isChecked() if hasattr(self, "_paid_checkbox") else False,
                notes=notes,
            )

            if editing_order_id is None:
                saved_order_id = int(order_service.save_order(order))
                success_message = "Order saved successfully."
            else:
                updated_order = order_service.update_order(editing_order_id, order)
                saved_order_id = int(getattr(updated_order, "id", editing_order_id))
                success_message = "Order updated successfully."
        except ValueError as exc:
            self._set_order_status(str(exc), error=True)
            return
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Failed to save order: {exc}", error=True)
            return

        if saved_order_id is None and editing_order_id is not None:
            saved_order_id = int(editing_order_id)

        if saved_order_id is not None:
            self._load_recent_orders(select_order_id=saved_order_id)
        else:
            self._load_recent_orders()
        self.refresh_dashboard()
        self._run_report()
        self._refresh_products()
        self._set_order_status(success_message)
        self._start_new_order(clear_status=False)
        self._update_order_action_buttons()

    def _clear_line_item_inputs(self) -> None:
        self._product_combo.setCurrentIndex(-1)
        self._product_combo.setCurrentText("")
        self._product_description_input.clear()
        self._quantity_input.setValue(1)
        self._unit_price_input.blockSignals(True)
        self._unit_price_input.setValue(0.00)
        self._unit_price_input.blockSignals(False)
        if hasattr(self, "_base_cost_input"):
            self._base_cost_input.blockSignals(True)
            self._base_cost_input.setValue(0.00)
            self._base_cost_input.blockSignals(False)
        self._current_cost_components = []
        if hasattr(self, "_line_price_type"):
            self._line_price_type.blockSignals(True)
            self._line_price_type.setCurrentIndex(0)
            self._line_price_type.blockSignals(False)
        self._product_combo.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_cost_summary()

    def _clear_order_form(self) -> None:
        self._order_number_input.setText(order_service.preview_next_order_number())
        self._customer_name_input.clear()
        self._customer_address_input.clear()
        self._order_date_input.setDate(QDate.currentDate())
        self._ship_date_input.blockSignals(True)
        self._ship_date_input.setDate(QDate.currentDate())
        self._ship_date_input.blockSignals(False)
        self._status_input.setCurrentIndex(0)
        self._set_paid_checkbox(False)
        self._carrier_input.clear()
        self._tracking_input.clear()
        self._target_completion_input.blockSignals(True)
        self._target_completion_input.setDate(QDate.currentDate())
        self._target_completion_input.blockSignals(False)
        if hasattr(self, "_order_notes_input"):
            self._order_notes_input.clear()

    def _set_order_status(self, message: str, *, error: bool = False) -> None:
        palette = "color: #d32f2f;" if error else "color: #2e7d32;"
        self._order_status_label.setStyleSheet(palette)
        self._order_status_label.setText(message)

    def _on_recent_order_selection_changed(self, current, _previous) -> None:
        row = current.row()
        if 0 <= row < len(self._recent_orders_cache):
            order = self._recent_orders_cache[row]
            order_id_value = getattr(order, "id", None)
            if order_id_value is not None:
                persisted = order_service.fetch_order(int(order_id_value))
                if persisted is not None:
                    order = persisted
            self._selected_order = order
            self._load_order_into_form(order)
        else:
            self._selected_order = None
            self._start_new_order()
        self._update_order_action_buttons()

    def _update_order_action_buttons(self) -> None:
        has_order = self._selected_order is not None and getattr(self._selected_order, "id", None) is not None
        if hasattr(self, "_cancel_order_button"):
            self._cancel_order_button.setEnabled(has_order)
        if hasattr(self, "_delete_order_button"):
            self._delete_order_button.setEnabled(has_order)
        if hasattr(self, "_export_invoice_button"):
            self._export_invoice_button.setEnabled(has_order)

    def _on_status_changed(self, status: str) -> None:
        if self._selected_order is not None:
            self._selected_order = replace(self._selected_order, status=status)

    def _on_paid_checkbox_changed(self, state: int) -> None:
        check_state = Qt.CheckState(state) if not isinstance(state, Qt.CheckState) else state
        should_be_paid = check_state == Qt.CheckState.Checked

        if self._selected_order is not None:
            self._selected_order = replace(self._selected_order, is_paid=should_be_paid)

    def _set_paid_checkbox(self, checked: bool) -> None:
        if not hasattr(self, "_paid_checkbox"):
            return
        blocker = QSignalBlocker(self._paid_checkbox)
        self._paid_checkbox.setChecked(bool(checked))
        del blocker

    def _handle_cancel_order(self) -> None:
        if self._selected_order is None or getattr(self._selected_order, "id", None) is None:
            self._show_message("Select an order before cancelling.")
            return

        confirm = QMessageBox.question(
            self,
            APP_NAME,
            f"Cancel order {self._selected_order.order_number}? This will restock its items.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        order_id_value = self._selected_order.id
        if order_id_value is None:
            self._show_message("Select an order before cancelling.")
            return
        order_id = int(order_id_value)

        try:
            order_service.cancel_order(order_id)
        except ValueError:
            self._set_order_status("Selected order could not be found.", error=True)
            self._load_recent_orders()
            return
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Failed to cancel order: {exc}", error=True)
            return

        self._set_order_status("Order cancelled.")
        self.refresh_dashboard()
        self._refresh_products()
        self._load_recent_orders()
        self._run_report()

    def _handle_delete_order(self) -> None:
        if self._selected_order is None or getattr(self._selected_order, "id", None) is None:
            self._show_message("Select an order before deleting.")
            return

        confirm = QMessageBox.question(
            self,
            APP_NAME,
            f"Delete order {self._selected_order.order_number}? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        order_id_value = self._selected_order.id
        if order_id_value is None:
            self._show_message("Select an order before deleting.")
            return
        order_id = int(order_id_value)

        try:
            order_service.delete_order(order_id)
        except ValueError:
            self._set_order_status("Selected order could not be found.", error=True)
            self._load_recent_orders()
            return
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Failed to delete order: {exc}", error=True)
            return

        self._set_order_status("Order deleted.")
        self.refresh_dashboard()
        self._refresh_products()
        self._load_recent_orders()
        self._run_report()

    def _handle_export_invoice(self) -> None:
        if self._selected_order is None or getattr(self._selected_order, "id", None) is None:
            self._show_message("Select a saved order before exporting an invoice.")
            return

        dialog = InvoiceManagerDialog(parent=self, app_settings=self._app_settings, order=self._selected_order)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_order_status("Invoice export cancelled.")
            return

        updated_settings = dialog.get_updated_settings()
        if updated_settings is not None:
            self._app_settings = updated_settings

        order_id_value = getattr(self._selected_order, "id", None)
        if order_id_value is None:
            self._set_order_status("Select a saved order before exporting an invoice.", error=True)
            return
        order_id = int(order_id_value)
        default_name = f"{self._selected_order.order_number}_invoice.pdf".replace(" ", "_")
        suggested_path = str(Path.home() / default_name)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Invoice",
            suggested_path,
            "PDF Files (*.pdf);;All Files (*)",
        )

        if not filename:
            self._set_order_status("Invoice export cancelled.")
            return

        try:
            exported_path = order_service.export_order_invoice(order_id, filename)
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Invoice export failed: {exc}", error=True)
            return

        self._set_order_status(f"Invoice saved to {exported_path}")

    def _on_report_range_changed(self, index: int) -> None:
        if not hasattr(self, "_report_range_input"):
            return

        key = self._report_range_input.itemData(index, Qt.ItemDataRole.UserRole)
        key_str = str(key or "")

        is_custom = key_str == "custom"
        self._report_start_date.setEnabled(is_custom)
        self._report_end_date.setEnabled(is_custom)

        if is_custom:
            return

        start, end = self._calculate_report_range(key_str)
        self._set_report_date_value(self._report_start_date, start)
        self._set_report_date_value(self._report_end_date, end)
        self._run_report()

    def _calculate_report_range(self, key: str) -> tuple[Optional[date], Optional[date]]:
        today = date.today()

        if key == "week":
            start = today - timedelta(days=today.weekday())
            return start, today

        if key == "month":
            start = today.replace(day=1)
            return start, today

        if key == "year":
            start = date(today.year, 1, 1)
            return start, today

        if key == "all":
            return None, None

        return None, None

    def _set_report_date_value(self, control: QDateEdit, value: Optional[date]) -> None:
        control.blockSignals(True)
        if value is None:
            control.setDate(QDate())
        else:
            control.setDate(QDate(value.year, value.month, value.day))
        control.blockSignals(False)

    def _handle_browse_logo(self) -> None:
        initial_dir = self._logo_path_input.text().strip() or str(Path.home())
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Dashboard Logo",
            initial_dir,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)",
        )
        if filename:
            self._logo_path_input.setText(filename)

    def _handle_clear_logo(self) -> None:
        self._logo_path_input.clear()
        self._settings_status_label.setText("Logo path cleared (save to apply).")

    def _open_invoice_manager(self) -> None:
        dialog = InvoiceManagerDialog(parent=self, app_settings=self._app_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_updated_settings()
            if updated is not None:
                self._app_settings = updated
                self._settings_status_label.setText("Invoice settings saved.")
                self.refresh_dashboard()

    def _normalize_home_state_input(self) -> None:
        if not hasattr(self, "_home_state_input"):
            return
        value = self._home_state_input.text().strip().upper()[:2]
        self._home_state_input.blockSignals(True)
        self._home_state_input.setText(value)
        self._home_state_input.blockSignals(False)

    def _normalize_home_city_input(self) -> None:
        if not hasattr(self, "_home_city_input"):
            return
        value = " ".join(segment for segment in self._home_city_input.text().strip().split())
        self._home_city_input.blockSignals(True)
        self._home_city_input.setText(value)
        self._home_city_input.blockSignals(False)

    def _handle_save_settings(self) -> None:
        updated = AppSettings(
            business_name=self._business_name_input.text().strip() or APP_NAME,
            low_inventory_threshold=self._low_inventory_input.value(),
            order_number_format=self._order_number_format_input.text().strip(),
            order_number_next=self._order_number_next_input.value(),
            dashboard_show_business_name=self._show_business_name_checkbox.isChecked(),
            dashboard_logo_path=self._logo_path_input.text().strip(),
            dashboard_logo_alignment=self._logo_alignment_combo.currentData() or "top-left",
            dashboard_logo_size=self._logo_size_input.value(),
            dashboard_home_city=self._home_city_input.text().strip(),
            dashboard_home_state=self._home_state_input.text().strip().upper()[:2],
            invoice_slogan=self._app_settings.invoice_slogan,
            invoice_street=self._app_settings.invoice_street,
            invoice_city=self._app_settings.invoice_city,
            invoice_state=self._app_settings.invoice_state,
            invoice_zip=self._app_settings.invoice_zip,
            invoice_phone=self._app_settings.invoice_phone,
            invoice_fax=self._app_settings.invoice_fax,
            invoice_terms=self._app_settings.invoice_terms,
            invoice_comments=self._app_settings.invoice_comments,
            invoice_contact_name=self._app_settings.invoice_contact_name,
            invoice_contact_phone=self._app_settings.invoice_contact_phone,
            invoice_contact_email=self._app_settings.invoice_contact_email,
            payment_options=list(self._app_settings.payment_options),
            payment_other=self._app_settings.payment_other,
            tax_rate_percent=self._tax_rate_input.value(),
            tax_show_on_invoice=self._tax_show_invoice_checkbox.isChecked(),
            tax_add_to_total=self._tax_include_total_checkbox.isChecked(),
        )
        self._app_settings = order_service.update_app_settings(updated)
        self._order_number_format_input.setText(self._app_settings.order_number_format)
        self._order_number_next_input.setValue(self._app_settings.order_number_next)
        self._show_business_name_checkbox.setChecked(self._app_settings.dashboard_show_business_name)
        self._logo_path_input.setText(self._app_settings.dashboard_logo_path)
        self._home_city_input.setText(self._app_settings.dashboard_home_city)
        self._home_state_input.setText(self._app_settings.dashboard_home_state)
        align_index = self._logo_alignment_combo.findData(self._app_settings.dashboard_logo_alignment)
        if align_index >= 0:
            self._logo_alignment_combo.setCurrentIndex(align_index)
        self._logo_size_input.setValue(self._app_settings.dashboard_logo_size)
        self._tax_rate_input.setValue(self._app_settings.tax_rate_percent)
        self._tax_show_invoice_checkbox.setChecked(self._app_settings.tax_show_on_invoice)
        self._tax_include_total_checkbox.setChecked(self._app_settings.tax_add_to_total)
        self._order_number_input.setText(order_service.preview_next_order_number())
        if self._product_manager_dialog is not None:
            self._product_manager_dialog.update_app_settings(self._app_settings)
        self._settings_status_label.setText("Settings saved.")
        self.refresh_dashboard()
        self._run_report()
        self._refresh_products()

    def _update_graphs(self, summary: Optional[List[Any]] = None) -> None:
        if summary is not None:
            data = list(summary)
        else:
            snapshot = order_service.get_dashboard_snapshot()
            data = list(snapshot.product_breakdown) if snapshot.product_breakdown else []

        chart = QChart()
        chart.setTitle("Product Sales Totals")

        series = QBarSeries()
        bar_set = QBarSet("Total Sales")
        categories: List[str] = []

        for row in data[:15]:
            categories.append(getattr(row, "product_name", ""))
            bar_set.append(float(getattr(row, "total_sales", 0.0)))

        if not categories:
            categories = ["No Data"]
            bar_set.append(0.0)

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("$%.0f")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        self._chart_view.setChart(chart)

    def _build_map_tab(self) -> None:
        layout = QVBoxLayout()
        self._map_tab.setLayout(layout)

        header_layout = QHBoxLayout()
        layout.addLayout(header_layout)

        title_label = QLabel("Shipping Destinations")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)

        self._map_lines_checkbox = QCheckBox("Show Connections")
        self._map_lines_checkbox.setChecked(True)
        self._map_lines_checkbox.toggled.connect(self._refresh_map)
        header_layout.addWidget(self._map_lines_checkbox)

        self._map_line_style = QComboBox()
        self._map_line_style.addItem("Curved Arcs", "curved")
        self._map_line_style.addItem("Straight Lines", "straight")
        self._map_line_style.setToolTip(
            "Choose whether to draw curved arcs or straight lines between home and destinations.",
        )
        self._map_line_style.currentIndexChanged.connect(lambda _index: self._refresh_map())
        header_layout.addWidget(self._map_line_style)

        self._map_line_pattern = QComboBox()
        self._map_line_pattern.addItem("Solid", "solid")
        self._map_line_pattern.addItem("Dashed", "dashed")
        self._map_line_pattern.setToolTip("Pick a stroke pattern for connection lines.")
        self._map_line_pattern.currentIndexChanged.connect(lambda _index: self._refresh_map())
        header_layout.addWidget(self._map_line_pattern)

        self._map_line_color = QComboBox()
        self._map_line_color.addItem("Deep Blue", "#3f51b5")
        self._map_line_color.addItem("Crimson", "#c62828")
        self._map_line_color.addItem("Teal", "#00897b")
        self._map_line_color.addItem("Amber", "#ff8f00")
        self._map_line_color.addItem("Purple", "#6a1b9a")
        self._map_line_color.setToolTip("Select the connection line color.")
        self._map_line_color.currentIndexChanged.connect(lambda _index: self._refresh_map())
        header_layout.addWidget(self._map_line_color)

        self._map_base_layer_combo = QComboBox()
        self._map_base_layer_combo.addItem("Light Basemap", "light")
        self._map_base_layer_combo.addItem("Dark Basemap", "dark")
        self._map_base_layer_combo.setToolTip("Switch between light and dark map backgrounds.")
        self._map_base_layer_combo.currentIndexChanged.connect(lambda _index: self._refresh_map())
        header_layout.addWidget(self._map_base_layer_combo)

        self._map_territory_checkbox = QCheckBox("Shade States")
        self._map_territory_checkbox.setToolTip("Color US states by shipment volume.")
        self._map_territory_checkbox.toggled.connect(self._refresh_map)
        header_layout.addWidget(self._map_territory_checkbox)

        header_layout.addStretch(1)

        refresh_button = QPushButton("Refresh Map")
        refresh_button.clicked.connect(self._refresh_map)
        header_layout.addWidget(refresh_button)

        self._map_status_label = QLabel("Loading map…")
        layout.addWidget(self._map_status_label)

        self._map_view = QWebEngineView()
        self._map_view.setHtml(self._build_placeholder_map_html("Collecting destination data…"))
        layout.addWidget(self._map_view, 1)

    # Helpers
    def _configure_table(self, table: QTableView) -> None:
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def _wrap_group(self, title: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout()
        container.setLayout(layout)
        label = QLabel(title)
        label.setStyleSheet("font-weight: bold;")
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

    def _show_message(self, message: str) -> None:
        QMessageBox.information(self, APP_NAME, message)

    @staticmethod
    def _extract_optional_date(control: QDateEdit) -> Optional[date]:
        value = control.date()
        if not value.isValid() or value == QDate():
            return None
        return date(value.year(), value.month(), value.day())


class NewProductDialog(QDialog):
    def __init__(self, *, suggested_name: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Product")
        self._sku_input = QLineEdit()
        self._name_input = QLineEdit(suggested_name)

        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.addRow("SKU", self._sku_input)
        form_layout.addRow("Product Name", self._name_input)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    @property
    def sku(self) -> str:
        return self._sku_input.text().strip().upper()

    @property
    def name(self) -> str:
        return self._name_input.text().strip() or self.sku

    def _on_accept(self) -> None:
        if not self.sku:
            QMessageBox.warning(self, APP_NAME, "SKU is required for a new product.")
            return
        self.accept()
