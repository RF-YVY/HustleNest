from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class OrderItem:
    product_name: str
    product_description: str
    quantity: int
    unit_price: float
    product_sku: str
    product_id: Optional[int] = None

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    order_number: str
    customer_name: str
    customer_address: str
    order_date: date
    status: str
    carrier: str = ""
    tracking_number: str = ""
    ship_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    id: Optional[int] = None
    items: List[OrderItem] = field(default_factory=list)

    @property
    def total_amount(self) -> float:
        return sum(item.line_total for item in self.items)


@dataclass
class ProductSalesSummary:
    product_name: str
    total_quantity: int
    total_sales: float


@dataclass
class CustomerSalesSummary:
    customer_name: str
    order_count: int
    total_sales: float
    average_order: float


@dataclass
class OutstandingOrder:
    id: int
    order_number: str
    customer_name: str
    order_date: date
    total_amount: float
    status: str
    carrier: str = ""
    tracking_number: str = ""
    target_completion_date: Optional[date] = None


@dataclass
class CompletedOrder:
    id: int
    order_number: str
    customer_name: str
    order_date: date
    ship_date: Optional[date]
    total_amount: float
    status: str
    carrier: str = ""
    tracking_number: str = ""
    target_completion_date: Optional[date] = None


@dataclass
class OrderReportRow:
    order_id: int
    order_number: str
    customer_name: str
    order_date: date
    ship_date: Optional[date]
    status: str
    total_amount: float
    products: str
    carrier: str = ""
    tracking_number: str = ""
    item_count: int = 0
    target_completion_date: Optional[date] = None


@dataclass
class OrderDestination:
    city: str
    state: str
    count: int
    order_numbers: List[str] = field(default_factory=list)


@dataclass
class DashboardSnapshot:
    total_sales: float
    outstanding_orders: int
    product_breakdown: List[ProductSalesSummary]
    outstanding_details: List[OutstandingOrder]
    completed_orders: int
    completed_details: List[CompletedOrder]
    top_customers: List[CustomerSalesSummary]
    inventory_forecast: List["ProductForecast"]


@dataclass
class Product:
    id: Optional[int]
    sku: str
    name: str
    description: str
    photo_path: str
    inventory_count: int
    is_complete: bool
    status: str


@dataclass
class AppSettings:
    business_name: str
    low_inventory_threshold: int
    order_number_format: str = "ORD-{seq:04d}"
    order_number_next: int = 1
    dashboard_show_business_name: bool = True
    dashboard_logo_path: str = ""
    dashboard_logo_alignment: str = "top-left"
    dashboard_logo_size: int = 160
    dashboard_home_city: str = ""
    dashboard_home_state: str = ""


@dataclass
class OrderHistoryEvent:
    id: int
    order_id: Optional[int]
    order_number: str
    event_type: str
    description: str
    amount_delta: float
    created_at: datetime


@dataclass
class ProductForecast:
    product_id: Optional[int]
    sku: str
    name: str
    status: str
    inventory_count: int
    average_weekly_sales: float
    days_until_stockout: Optional[int]
    needs_reorder: bool = False


@dataclass
class NotificationMessage:
    category: str
    message: str
    severity: str = "info"
