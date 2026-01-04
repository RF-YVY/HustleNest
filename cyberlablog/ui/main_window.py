from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, List, Optional

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QVBoxLayout,
    QWidget,
)

from ..models.order_models import AppSettings, NotificationMessage, Order, OrderItem, OrderReportRow, Product
from ..resources import get_app_icon_path
from ..services import order_service
from ..versioning import APP_VERSION, RELEASES_URL, REPOSITORY_URL, check_for_updates
from ..viewmodels.table_models import ListTableModel


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
        self._selected_product: Optional[Product] = None
        self._selected_order: Optional[Order] = None
        self._app_settings: AppSettings = order_service.get_app_settings()
        self._status_options: List[str] = order_service.list_order_statuses()
        self._product_status_options: List[str] = order_service.list_product_statuses()

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

        self._tab_widget.addTab(self._dashboard_tab, "Dashboard")
        self._tab_widget.addTab(self._orders_tab, "Orders")
        self._tab_widget.addTab(self._reports_tab, "Reports")
        self._tab_widget.addTab(self._history_tab, "History")
        self._tab_widget.addTab(self._products_tab, "Products")
        self._tab_widget.addTab(self._graphs_tab, "Graphs")
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
        self._pending_items_model: ListTableModel
        self._pending_items_table: QTableView
        self._recent_orders_model: ListTableModel
        self._recent_orders_table: QTableView
        self._customer_table: QTableView
        self._forecast_table: QTableView
        self._notifications_table: QTableView
        self._order_status_label: QLabel
        self._carrier_input: QLineEdit
        self._tracking_input: QLineEdit
        self._cancel_order_button: QPushButton
        self._delete_order_button: QPushButton

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

        self._products_model: ListTableModel
        self._products_table: QTableView
        self._product_sku_label: QLabel
        self._product_name_input: QLineEdit
        self._product_description_text: QTextEdit
        self._product_photo_input: QLineEdit
        self._product_inventory_input: QSpinBox
        self._product_status_combo: QComboBox
        self._product_alert_hint: QLabel

        self._business_name_input: QLineEdit
        self._low_inventory_input: QSpinBox
        self._settings_status_label: QLabel

        self._chart_view: QChartView
        self._completed_table: QTableView
        self._update_status_label: QLabel

        self._build_dashboard_tab()
        self._build_orders_tab()
        self._build_reports_tab()
        self._build_history_tab()
        self._build_products_tab()
        self._build_graphs_tab()
        self._build_settings_tab()
        self._build_about_tab()

        self._refresh_products()
        self.refresh_dashboard()
        self._load_recent_orders()
        QTimer.singleShot(0, self._check_for_updates)
        self._run_report()
        self._load_history()
        self._update_graphs()

    # Dashboard tab
    def _build_dashboard_tab(self) -> None:
        layout = QVBoxLayout()
        self._dashboard_tab.setLayout(layout)

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

    # Orders tab
    def _build_orders_tab(self) -> None:
        layout = QVBoxLayout()
        self._orders_tab.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self._order_number_input = QLineEdit()
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
        self._ship_date_input.setDate(QDate())
        form_layout.addRow("Ship Date", self._ship_date_input)

        self._target_completion_input = QDateEdit()
        self._target_completion_input.setCalendarPopup(True)
        self._target_completion_input.setSpecialValueText("No Target")
        self._target_completion_input.setDate(QDate())
        form_layout.addRow("Target Complete By", self._target_completion_input)

        self._status_input = QComboBox()
        self._status_input.addItems(self._status_options)
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
        product_selection_layout.addWidget(self._unit_price_input)

        add_item_button = QPushButton("Add Item")
        add_item_button.clicked.connect(self._handle_add_item)
        product_selection_layout.addWidget(add_item_button)

        remove_item_button = QPushButton("Remove Selected")
        remove_item_button.clicked.connect(self._handle_remove_item)
        product_selection_layout.addWidget(remove_item_button)

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
        self._report_start_date.setDate(QDate())
        filter_layout.addWidget(self._report_start_date)

        self._report_end_date = QDateEdit()
        self._report_end_date.setCalendarPopup(True)
        self._report_end_date.setSpecialValueText("End Date")
        self._report_end_date.setDate(QDate())
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
        self._products_tab.setLayout(layout)

        self._forecast_model = ListTableModel(
            (
                ("Product", lambda row: getattr(row, "name", "")),
                ("SKU", lambda row: getattr(row, "sku", "")),
                ("Inventory", lambda row: getattr(row, "inventory_count", "")),
                (
                    "Avg Weekly",
                    lambda row: f"{getattr(row, 'average_weekly_sales', 0.0):,.1f}",
                ),
                (
                    "Days Left",
                    lambda row: (
                        getattr(row, "days_until_stockout", None)
                        if getattr(row, "days_until_stockout", None) is not None
                        else "∞"
                    ),
                ),
                ("Status", lambda row: getattr(row, "status", "")),
                (
                    "Action",
                    lambda row: "Reorder" if getattr(row, "needs_reorder", False) else "",
                ),
            )
        )
        self._forecast_table = QTableView()
        self._forecast_table.setModel(self._forecast_model)
        self._configure_table(self._forecast_table)
        layout.addWidget(self._wrap_group("Inventory Forecast", self._forecast_table))

        self._products_model = ListTableModel(
            (
                ("SKU", lambda product: getattr(product, "sku", "")),
                ("Name", lambda product: getattr(product, "name", "")),
                ("Inventory", lambda product: getattr(product, "inventory_count", "")),
                ("Status", lambda product: getattr(product, "status", "")),
                (
                    "Alerts",
                    lambda product: self._product_alert_text(product)
                    if isinstance(product, Product)
                    else "",
                ),
                ("Description", lambda product: getattr(product, "description", "")),
            )
        )
        self._products_table = QTableView()
        self._products_table.setModel(self._products_model)
        self._configure_table(self._products_table)
        layout.addWidget(self._products_table, stretch=1)

        selection_model = self._products_table.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_product_selection_changed)

        form_group = QWidget()
        form_layout = QFormLayout()
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self._product_sku_label = QLabel("-")
        form_layout.addRow("SKU", self._product_sku_label)

        self._product_name_input = QLineEdit()
        form_layout.addRow("Name", self._product_name_input)

        self._product_description_text = QTextEdit()
        self._product_description_text.setFixedHeight(80)
        form_layout.addRow("Description", self._product_description_text)

        photo_layout = QHBoxLayout()
        self._product_photo_input = QLineEdit()
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._handle_browse_photo)
        photo_layout.addWidget(self._product_photo_input)
        photo_layout.addWidget(browse_button)
        form_layout.addRow("Photo Path", photo_layout)

        self._product_inventory_input = QSpinBox()
        self._product_inventory_input.setMaximum(1_000_000)
        form_layout.addRow("Inventory", self._product_inventory_input)

        self._product_status_combo = QComboBox()
        self._product_status_combo.addItems(self._product_status_options)
        form_layout.addRow("Status", self._product_status_combo)

        self._product_alert_hint = QLabel()
        form_layout.addRow("Alerts", self._product_alert_hint)

        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        new_button = QPushButton("New Product")
        new_button.clicked.connect(self._handle_product_new)
        button_layout.addWidget(new_button)

        save_button = QPushButton("Save Changes")
        save_button.clicked.connect(self._handle_product_save)
        button_layout.addWidget(save_button)

        delete_button = QPushButton("Delete Product")
        delete_button.clicked.connect(self._handle_product_delete)
        button_layout.addWidget(delete_button)

        button_layout.addStretch(1)

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

        self._low_inventory_input = QSpinBox()
        self._low_inventory_input.setMinimum(0)
        self._low_inventory_input.setMaximum(10_000)
        self._low_inventory_input.setValue(self._app_settings.low_inventory_threshold)
        form_layout.addRow("Low Inventory Threshold", self._low_inventory_input)

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
        about_html = (
            f"<h2>{APP_NAME} {APP_VERSION}</h2>"
            "<p>HustleNest centralizes order tracking, fulfillment workflows, and revenue analytics for"
            " growing makers and boutique sellers.</p>"
            "<h3>Highlights</h3>"
            "<ul>"
            "<li>Capture detailed orders with target completion dates, shipping partners, and tracking numbers.</li>"
            "<li>Monitor dashboards, low-inventory alerts, and overdue order notifications in one view.</li>"
            "<li>Review customer history, analytics, and exportable reports for bookkeeping.</li>"
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
    def refresh_dashboard(self) -> None:
        snapshot = order_service.get_dashboard_snapshot()
        self._total_sales_label.setText(f"Total Sales: ${snapshot.total_sales:,.2f}")
        self._outstanding_label.setText(f"Outstanding Orders: {snapshot.outstanding_orders}")
        self._completed_label.setText(f"Completed Orders: {snapshot.completed_orders}")
        self._product_model.update_rows(snapshot.product_breakdown)
        self._customer_model.update_rows(snapshot.top_customers)
        self._outstanding_model.update_rows(snapshot.outstanding_details)
        self._completed_model.update_rows(snapshot.completed_details)
        if hasattr(self, "_forecast_model"):
            self._forecast_model.update_rows(snapshot.inventory_forecast)
        if hasattr(self, "_notifications_model"):
            self._load_notifications()
        self._update_graphs(snapshot.product_breakdown)
        self._load_history()

    def _load_recent_orders(self) -> None:
        orders = order_service.list_recent_orders()
        self._recent_orders_cache = orders
        self._recent_orders_model.update_rows(self._recent_orders_cache)
        if hasattr(self, "_recent_orders_table"):
            self._recent_orders_table.clearSelection()
        self._selected_order = None
        self._update_order_action_buttons()

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
        target_sku = select_sku or (self._selected_product.sku if self._selected_product else None)

        self._products_cache = order_service.list_products()
        self._products_model.update_rows(self._products_cache)
        self._update_product_combo(select_sku=target_sku)

        if hasattr(self, "_forecast_model"):
            forecasts = order_service.list_inventory_forecast()
            self._forecast_model.update_rows(forecasts)
            self._load_notifications()

        self._selected_product = None
        if target_sku:
            for row_index, product in enumerate(self._products_cache):
                if product.sku == target_sku:
                    self._selected_product = product
                    self._select_product_row(row_index)
                    break

        if self._selected_product is None:
            self._products_table.clearSelection()

        self._update_product_form(self._selected_product)

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

    # Orders actions
    def _handle_add_item(self) -> None:
        product = self._resolve_selected_product()
        if product is None:
            return

        description = self._product_description_input.text().strip()
        quantity = self._quantity_input.value()
        unit_price = self._unit_price_input.value()

        if quantity <= 0:
            self._show_message("Quantity must be greater than zero.")
            return

        if unit_price <= 0:
            self._show_message("Unit price must be greater than zero.")
            return

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
            "New product added. Please complete details on the Products tab.",
        )
        return product

    def _handle_remove_item(self) -> None:
        index = self._pending_items_table.currentIndex()
        if not index.isValid():
            return
        del self._pending_items[index.row()]
        self._pending_items_model.update_rows(self._pending_items)

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
            order_service.save_order(order)
        except Exception as exc:  # noqa: BLE001
            self._set_order_status(f"Failed to save order: {exc}", error=True)
            return

        self._set_order_status("Order saved successfully.")
        self._pending_items.clear()
        self._pending_items_model.clear()
        self._clear_order_form()
        self.refresh_dashboard()
        self._load_recent_orders()
        self._run_report()
        self._refresh_products()

    def _clear_line_item_inputs(self) -> None:
        self._product_combo.setCurrentIndex(-1)
        self._product_combo.setCurrentText("")
        self._product_description_input.clear()
        self._quantity_input.setValue(1)
        self._unit_price_input.setValue(0.00)
        self._product_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _clear_order_form(self) -> None:
        self._order_number_input.clear()
        self._customer_name_input.clear()
        self._customer_address_input.clear()
        self._order_date_input.setDate(QDate.currentDate())
        self._ship_date_input.setDate(QDate())
        self._status_input.setCurrentIndex(0)
        self._carrier_input.clear()
        self._tracking_input.clear()
        self._target_completion_input.setDate(QDate())

    def _set_order_status(self, message: str, *, error: bool = False) -> None:
        palette = "color: #d32f2f;" if error else "color: #2e7d32;"
        self._order_status_label.setStyleSheet(palette)
        self._order_status_label.setText(message)

    def _on_recent_order_selection_changed(self, current, _previous) -> None:
        row = current.row()
        if 0 <= row < len(self._recent_orders_cache):
            self._selected_order = self._recent_orders_cache[row]
        else:
            self._selected_order = None
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

    # Reports actions
    def _on_product_selection_changed(self, current, _previous) -> None:
        row = current.row()
        if 0 <= row < len(self._products_cache):
            self._selected_product = self._products_cache[row]
        else:
            self._selected_product = None
        self._update_product_form(self._selected_product)

    def _update_product_form(self, product: Optional[Product]) -> None:
        if product is None:
            self._product_sku_label.setText("-")
            self._product_name_input.clear()
            self._product_description_text.clear()
            self._product_photo_input.clear()
            self._product_inventory_input.setValue(0)
            self._product_status_combo.blockSignals(True)
            self._product_status_combo.setCurrentIndex(0)
            self._product_status_combo.blockSignals(False)
            self._product_alert_hint.clear()
            return

        self._product_sku_label.setText(product.sku)
        self._product_name_input.setText(product.name)
        self._product_description_text.setText(product.description)
        self._product_photo_input.setText(product.photo_path)
        self._product_inventory_input.setValue(product.inventory_count)
        self._product_status_combo.blockSignals(True)
        combo_index = self._product_status_combo.findText(
            product.status,
            Qt.MatchFlag.MatchFixedString,
        )
        self._product_status_combo.setCurrentIndex(combo_index if combo_index >= 0 else 0)
        self._product_status_combo.blockSignals(False)
        self._product_alert_hint.setText(self._product_alert_text(product))

    def _handle_product_new(self) -> None:
        self._products_table.clearSelection()
        self._selected_product = None
        self._update_product_form(None)
        self._product_name_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _handle_product_save(self) -> None:
        if self._selected_product is None:
            self._show_message("Select a product from the list to update, or add it from the Orders tab.")
            return

        description_text = self._product_description_text.toPlainText().strip()
        photo_path = self._product_photo_input.text().strip()
        status = self._product_status_combo.currentText().strip()

        updated = replace(
            self._selected_product,
            name=self._product_name_input.text().strip() or self._selected_product.sku,
            description=description_text,
            photo_path=photo_path,
            inventory_count=self._product_inventory_input.value(),
            is_complete=self._is_product_complete(
                description_text,
                photo_path,
            ),
            status=status,
        )

        saved = order_service.update_product(updated)
        self._refresh_products(select_sku=saved.sku)
        self._show_message("Product details saved.")

    def _handle_product_delete(self) -> None:
        if self._selected_product is None or self._selected_product.id is None:
            self._show_message("Select a product from the list before deleting.")
            return

        confirm = QMessageBox.question(
            self,
            APP_NAME,
            f"Delete {self._selected_product.name}? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            order_service.delete_product(self._selected_product.id)
        except Exception as exc:  # noqa: BLE001
            self._show_message(f"Failed to delete product: {exc}")
            return

        self._show_message("Product deleted.")
        self._refresh_products()

    def _handle_browse_photo(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Product Photo",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if filename:
            self._product_photo_input.setText(filename)

    def _product_alert_text(self, product: Product) -> str:
        parts: List[str] = []
        status = (product.status or "").strip()

        if status and status.lower() in {"discontinued", "out of stock"}:
            parts.append(status.title())

        if not product.is_complete:
            parts.append("Needs Details")

        if product.inventory_count <= self._app_settings.low_inventory_threshold:
            parts.append("Low Inventory")

        if not parts:
            return "Ready"

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_parts = []
        for part in parts:
            upper_part = part.upper()
            if upper_part in seen:
                continue
            seen.add(upper_part)
            unique_parts.append(part)

        return ", ".join(unique_parts)

    def _is_product_complete(self, description: str, photo_path: str) -> bool:
        return bool(description.strip()) and bool(photo_path.strip())

    def _select_product_row(self, row_index: int) -> None:
        if 0 <= row_index < self._products_model.rowCount():
            self._products_table.selectRow(row_index)
            index = self._products_model.index(row_index, 0)
            self._products_table.scrollTo(index)

    def _handle_save_settings(self) -> None:
        updated = AppSettings(
            business_name=self._business_name_input.text().strip() or APP_NAME,
            low_inventory_threshold=self._low_inventory_input.value(),
        )
        self._app_settings = order_service.update_app_settings(updated)
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
