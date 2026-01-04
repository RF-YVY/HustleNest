from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from ..models.order_models import AppSettings, NotificationMessage, Order, OrderItem, OrderReportRow, Product
from ..resources import get_app_icon_path
from ..services import order_service
from ..versioning import APP_VERSION, RELEASES_URL, REPOSITORY_URL, check_for_updates
from ..viewmodels.table_models import ListTableModel
from .product_manager import ProductManagerDialog


APP_NAME = "HustleNest"


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
        self._order_date_input: QDateEdit
        self._ship_date_input: QDateEdit
        self._target_completion_input: QDateEdit
        self._status_input: QComboBox
        self._product_combo: QComboBox
        self._product_description_input: QLineEdit
        self._quantity_input: QSpinBox
        self._unit_price_input: QDoubleSpinBox
        self._line_price_type: QComboBox
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

        self._report_start_date: QDateEdit
        self._report_end_date: QDateEdit
        self._report_range_input: QComboBox
        self._report_model: ListTableModel
        self._report_status_label: QLabel
        self._reports_header_label: QLabel
        self._report_summary_label: QLabel
        self._report_export_button: QPushButton
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
                ("Total", lambda row: f"${getattr(row, 'total_amount', 0):,.2f}"),
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
                ("Total", lambda row: f"${getattr(row, 'total_amount', 0):,.2f}"),
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
        form_layout.addRow("Status", self._status_input)

        self._carrier_input = QLineEdit()
        self._carrier_input.setPlaceholderText("Carrier (e.g., UPS)")
        form_layout.addRow("Carrier", self._carrier_input)

        self._tracking_input = QLineEdit()
        self._tracking_input.setPlaceholderText("Tracking Number")
        form_layout.addRow("Tracking #", self._tracking_input)

        product_selection_layout = QHBoxLayout()
        layout.addLayout(product_selection_layout)

        self._product_combo = QComboBox()
        self._product_combo.setEditable(True)
        self._product_combo.setPlaceholderText("Select or type a product")
        self._product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        product_selection_layout.addWidget(self._product_combo, stretch=3)

        self._product_description_input = QLineEdit()
        self._product_description_input.setPlaceholderText("Line item description")
        product_selection_layout.addWidget(self._product_description_input, stretch=3)

        self._quantity_input = QSpinBox()
        self._quantity_input.setMinimum(1)
        self._quantity_input.setMaximum(1_000_000)
        self._quantity_input.setValue(1)
        product_selection_layout.addWidget(self._quantity_input)

        self._unit_price_input = QDoubleSpinBox()
        self._unit_price_input.setPrefix("$")
        self._unit_price_input.setDecimals(2)
        self._unit_price_input.setMaximum(1_000_000)
        self._unit_price_input.setValue(0.00)
        self._unit_price_input.valueChanged.connect(self._on_unit_price_changed)
        product_selection_layout.addWidget(self._unit_price_input)

        self._line_price_type = QComboBox()
        self._line_price_type.addItems(["Standard", "FREEBIE"])
        self._line_price_type.setCurrentIndex(0)
        self._line_price_type.currentTextChanged.connect(self._on_price_type_changed)
        product_selection_layout.addWidget(self._line_price_type)

        add_item_button = QPushButton("Add Item")
        add_item_button.clicked.connect(self._handle_add_item)
        product_selection_layout.addWidget(add_item_button)

        remove_item_button = QPushButton("Remove Selected")
        remove_item_button.clicked.connect(self._handle_remove_item)
        product_selection_layout.addWidget(remove_item_button)

        manage_products_button = QPushButton("Manage Products")
        manage_products_button.clicked.connect(self._open_product_manager)
        product_selection_layout.addWidget(manage_products_button)

        items_layout = QHBoxLayout()
        layout.addLayout(items_layout, stretch=1)

        self._pending_items_model = ListTableModel(
            (
                ("Product", lambda row: getattr(row, "product_name", "")),
                ("SKU", lambda row: getattr(row, "product_sku", "")),
                ("Description", lambda row: getattr(row, "product_description", "")),
                ("Quantity", lambda row: getattr(row, "quantity", "")),
                ("Unit Price", lambda row: f"${getattr(row, 'unit_price', 0):,.2f}"),
                ("Line Total", lambda row: f"${getattr(row, 'line_total', 0):,.2f}"),
            )
        )
        self._pending_items_table = QTableView()
        self._pending_items_table.setModel(self._pending_items_model)
        self._configure_table(self._pending_items_table)
        items_layout.addWidget(self._wrap_group("Pending Items", self._pending_items_table), stretch=3)

        self._recent_orders_model = ListTableModel(
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
                ("Status", lambda row: getattr(row, "status", "")),
                ("Carrier", lambda row: getattr(row, "carrier", "")),
                ("Tracking #", lambda row: getattr(row, "tracking_number", "")),
                ("Total", lambda row: f"${getattr(row, 'total_amount', 0):,.2f}"),
            )
        )
        self._recent_orders_table = QTableView()
        self._recent_orders_table.setModel(self._recent_orders_model)
        self._configure_table(self._recent_orders_table)
        items_layout.addWidget(self._wrap_group("Recent Orders", self._recent_orders_table), stretch=2)

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
                ("Total", lambda row: f"${getattr(row, 'total_amount', 0):,.2f}"),
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
        self._history_start_filter.setDate(QDate())
        filter_layout.addWidget(self._history_start_filter)

        self._history_end_filter = QDateEdit()
        self._history_end_filter.setCalendarPopup(True)
        self._history_end_filter.setSpecialValueText("End Date")
        self._history_end_filter.setDate(QDate())
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
        self._history_start_filter.setDate(QDate())
        self._history_end_filter.setDate(QDate())
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
            "and capture shipping details. Use the Recent Orders list to select an order for editing, cancelling, or deletion.</p>"
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
        self._total_sales_label.setText(f"Total Sales: ${snapshot.total_sales:,.2f}")
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

    def _load_recent_orders(self) -> None:
        orders = order_service.list_recent_orders()
        self._recent_orders_cache = orders
        self._recent_orders_model.update_rows(self._recent_orders_cache)
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
        if hasattr(self, "_product_combo"):
            self._product_combo.setCurrentIndex(-1)
            self._product_combo.setCurrentText("")
        if hasattr(self, "_product_description_input"):
            self._product_description_input.clear()
        if hasattr(self, "_quantity_input"):
            self._quantity_input.setValue(1)
        if hasattr(self, "_unit_price_input"):
            self._unit_price_input.setValue(0.00)

        if clear_status and hasattr(self, "_order_status_label"):
            self._order_status_label.setStyleSheet("")
            self._order_status_label.clear()

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

        self._carrier_input.setText(order.carrier)
        self._tracking_input.setText(order.tracking_number)

        self._pending_items = [replace(item) for item in order.items]
        self._pending_items_model.update_rows(self._pending_items)
        if hasattr(self, "_pending_items_table"):
            self._pending_items_table.clearSelection()

        if hasattr(self, "_line_price_type"):
            self._line_price_type.blockSignals(True)
            self._line_price_type.setCurrentIndex(0)
            self._line_price_type.blockSignals(False)

        self._product_combo.setCurrentIndex(-1)
        self._product_combo.setCurrentText("")
        self._product_description_input.clear()
        self._quantity_input.setValue(1)
        self._unit_price_input.blockSignals(True)
        self._unit_price_input.setValue(0.00)
        self._unit_price_input.blockSignals(False)

        self._order_status_label.setStyleSheet("color: #1976d2;")
        self._order_status_label.setText("Editing existing order. Save to apply changes.")

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
        total_items = sum(getattr(row, "item_count", 0) for row in self._current_report_rows)
        summary_text = f"Orders: {order_count} | Items: {total_items} | Sales: ${total_sales:,.2f}"
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

        status_style = "color: #ef6c00;" if home_error else ""
        self._map_status_label.setStyleSheet(status_style)
        self._map_status_label.setText(" ".join(status_parts))
        self._map_view.setHtml(self._build_map_html(markers, home_location))

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
    def _build_map_html(markers: List[Dict[str, Any]], home_location: Optional[Dict[str, Any]]) -> str:
        markers_json = json.dumps(markers)
        home_json = json.dumps(home_location) if home_location else "null"

        return (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset=\"utf-8\"/>"
            "<title>Order Destinations</title>"
            "<link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\"/>"
            "<style>html, body, #map { height: 100%; margin: 0; }"
            " .connector { stroke-dasharray: 4 6; }</style>"
            "</head><body><div id=\"map\"></div>"
            "<script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>"
            "<script>"
            f"const markers = {markers_json};"
            f"const homeLocation = {home_json};"
            "const map = L.map('map');"
            "L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {"
            "    maxZoom: 18,"
            "    attribution: '&copy; OpenStreetMap contributors'"
            "}).addTo(map);"
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
            "if (homeLocation && markers.length) {"
            "    const origin = [homeLocation.lat, homeLocation.lon];"
            "    markers.forEach((item, index) => {"
            "        const arcPoints = buildArcPoints(origin, [item.lat, item.lon], index);"
            "        L.polyline(arcPoints, { color: '#3f51b5', weight: 2, opacity: 0.6 }).addTo(map);"
            "    });"
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
        product = self._resolve_selected_product()
        if product is None:
            return

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

        item = OrderItem(
            product_name=product.name,
            product_description=description,
            quantity=quantity,
            unit_price=unit_price,
            product_sku=product.sku,
            product_id=product.id,
        )
        self._pending_items.append(item)
        self._pending_items_model.update_rows(self._pending_items)
        self._clear_line_item_inputs()

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
        del self._pending_items[index.row()]
        self._pending_items_model.update_rows(self._pending_items)

    def _on_unit_price_changed(self, value: float) -> None:
        if not hasattr(self, "_line_price_type"):
            return

        is_zero = abs(float(value)) < 0.005
        target_text = "FREEBIE" if is_zero else "Standard"

        if self._line_price_type.currentText().lower() == target_text.lower():
            return

        self._line_price_type.blockSignals(True)
        self._line_price_type.setCurrentText(target_text)
        self._line_price_type.blockSignals(False)

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
        order_date = self._extract_optional_date(self._order_date_input) or date.today()
        ship_date = self._extract_optional_date(self._ship_date_input)
        target_completion = self._extract_optional_date(self._target_completion_input)

        if target_completion and target_completion < order_date:
            self._set_order_status("Target completion date cannot be before the order date.", error=True)
            return

        editing_order_id = self._editing_order_id

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
            )

            if editing_order_id is None:
                order_service.save_order(order)
                success_message = "Order saved successfully."
            else:
                order_service.update_order(editing_order_id, order)
                success_message = "Order updated successfully."
        except ValueError as exc:
            self._set_order_status(str(exc), error=True)
            return
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Failed to save order: {exc}", error=True)
            return

        self._load_recent_orders()
        self.refresh_dashboard()
        self._run_report()
        self._refresh_products()
        self._set_order_status(success_message)

    def _clear_line_item_inputs(self) -> None:
        self._product_combo.setCurrentIndex(-1)
        self._product_combo.setCurrentText("")
        self._product_description_input.clear()
        self._quantity_input.setValue(1)
        self._unit_price_input.blockSignals(True)
        self._unit_price_input.setValue(0.00)
        self._unit_price_input.blockSignals(False)
        if hasattr(self, "_line_price_type"):
            self._line_price_type.blockSignals(True)
            self._line_price_type.setCurrentIndex(0)
            self._line_price_type.blockSignals(False)
        self._product_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _clear_order_form(self) -> None:
        self._order_number_input.setText(order_service.preview_next_order_number())
        self._customer_name_input.clear()
        self._customer_address_input.clear()
        self._order_date_input.setDate(QDate.currentDate())
        self._ship_date_input.blockSignals(True)
        self._ship_date_input.setDate(QDate.currentDate())
        self._ship_date_input.blockSignals(False)
        self._status_input.setCurrentIndex(0)
        self._carrier_input.clear()
        self._tracking_input.clear()
        self._target_completion_input.blockSignals(True)
        self._target_completion_input.setDate(QDate.currentDate())
        self._target_completion_input.blockSignals(False)

    def _set_order_status(self, message: str, *, error: bool = False) -> None:
        palette = "color: #d32f2f;" if error else "color: #2e7d32;"
        self._order_status_label.setStyleSheet(palette)
        self._order_status_label.setText(message)

    def _on_recent_order_selection_changed(self, current, _previous) -> None:
        row = current.row()
        if 0 <= row < len(self._recent_orders_cache):
            order = self._recent_orders_cache[row]
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
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
