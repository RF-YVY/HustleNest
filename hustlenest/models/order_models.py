from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class CostComponent:
    label: str
    amount: float


@dataclass
class OrderItem:
    product_name: str
    product_description: str
    quantity: int
    unit_price: float
    product_sku: str
    product_id: Optional[int] = None
    base_unit_cost: float = 0.0
    cost_components: List[CostComponent] = field(default_factory=list)
    is_freebie: bool = False
    applied_discount: float = 0.0
    applied_tax: float = 0.0
    price_adjustment_note: str = ""

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price

    @property
    def additional_unit_cost(self) -> float:
        return sum(component.amount for component in self.cost_components)

    @property
    def unit_cost(self) -> float:
        return self.base_unit_cost + self.additional_unit_cost

    @property
    def line_cost(self) -> float:
        return self.unit_cost * self.quantity

    @property
    def line_profit(self) -> float:
        return self.line_total - self.line_cost

    @property
    def margin(self) -> float:
        total = self.line_total
        if total == 0:
            return 0.0
        return self.line_profit / total

    @property
    def adjustment_summary(self) -> str:
        segments: List[str] = []
        discount = float(self.applied_discount or 0.0)
        tax = float(self.applied_tax or 0.0)
        if discount > 0.005:
            segments.append(f"Discount -${discount:,.2f}")
        if tax > 0.005:
            segments.append(f"Tax +${tax:,.2f}")
        note = (self.price_adjustment_note or "").strip()
        if note:
            segments.append(note)
        return "; ".join(segments)


@dataclass
class Order:
    order_number: str
    customer_name: str
    customer_address: str
    order_date: date
    status: str
    is_paid: bool = False
    carrier: str = ""
    tracking_number: str = ""
    notes: str = ""
    ship_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    id: Optional[int] = None
    items: List[OrderItem] = field(default_factory=list)
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    tax_included_in_total: bool = False

    @property
    def total_amount(self) -> float:
        return sum(item.line_total for item in self.items)

    @property
    def total_cost(self) -> float:
        return sum(item.line_cost for item in self.items)

    @property
    def total_profit(self) -> float:
        return self.total_amount - self.total_cost

    @property
    def profit_margin(self) -> float:
        total = self.total_amount
        if total == 0:
            return 0.0
        return self.total_profit / total

    @property
    def total_with_tax(self) -> float:
        return self.total_amount + self.tax_amount

    @property
    def display_total(self) -> float:
        return self.total_amount + (self.tax_amount if self.tax_included_in_total else 0.0)

    @property
    def effective_tax_rate(self) -> float:
        subtotal = self.total_amount
        if subtotal <= 0:
            return 0.0
        return self.tax_amount / subtotal


@dataclass
class ProductSalesSummary:
    product_name: str
    total_quantity: int
    total_sales: float
    total_cost: float = 0.0
    total_profit: float = 0.0
    margin: float = 0.0


@dataclass
class CustomerSalesSummary:
    customer_name: str
    order_count: int
    total_sales: float
    average_order: float
    total_cost: float = 0.0
    total_profit: float = 0.0
    margin: float = 0.0


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
    notes: str = ""
    target_completion_date: Optional[date] = None
    tax_amount: float = 0.0
    tax_included_in_total: bool = False

    @property
    def display_total(self) -> float:
        return self.total_amount + (self.tax_amount if self.tax_included_in_total else 0.0)


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
    notes: str = ""
    target_completion_date: Optional[date] = None
    tax_amount: float = 0.0
    tax_included_in_total: bool = False

    @property
    def display_total(self) -> float:
        return self.total_amount + (self.tax_amount if self.tax_included_in_total else 0.0)


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
    notes: str = ""
    item_count: int = 0
    target_completion_date: Optional[date] = None
    total_cost: float = 0.0
    profit: float = 0.0
    margin: float = 0.0
    freebie_cost: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    tax_included_in_total: bool = False
    adjustment_summary: str = ""

    @property
    def net_revenue(self) -> float:
        return self.total_amount - self.freebie_cost

    @property
    def total_with_tax(self) -> float:
        return self.total_amount + self.tax_amount

    @property
    def display_total(self) -> float:
        return self.total_amount + (self.tax_amount if self.tax_included_in_total else 0.0)


@dataclass
class SalesTaxSummary:
    period_label: str
    period_start: date
    period_end: date
    order_count: int
    taxable_sales: float
    display_sales: float
    tax_rate_percent: float
    tax_collected: float
    expected_tax: float
    difference: float


@dataclass
class OrderDestination:
    city: str
    state: str
    count: int
    order_numbers: List[str] = field(default_factory=list)


@dataclass
class DashboardSnapshot:
    total_sales: float
    total_cost: float
    total_profit: float
    profit_margin: float
    outstanding_orders: int
    product_breakdown: List[ProductSalesSummary]
    outstanding_details: List[OutstandingOrder]
    completed_orders: int
    completed_details: List[CompletedOrder]
    top_customers: List[CustomerSalesSummary]
    inventory_forecast: List["ProductForecast"]
    net_sales: float = 0.0
    freebie_cost: float = 0.0
    tax_total: float = 0.0
    paid_sales: float = 0.0
    unpaid_sales: float = 0.0
    loss_total: float = 0.0
    expense_total: float = 0.0
    materials_value: float = 0.0
    cash_flow_projection_30: float = 0.0
    inventory_alerts: List["NotificationMessage"] = field(default_factory=list)
    crm_followups: List["CRMContact"] = field(default_factory=list)
    goal_status: List["BusinessGoal"] = field(default_factory=list)


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
    base_unit_cost: float = 0.0
    default_unit_price: float = 0.0
    pricing_components: List[CostComponent] = field(default_factory=list)

    @property
    def additional_unit_cost(self) -> float:
        return sum(component.amount for component in self.pricing_components)

    @property
    def total_unit_cost(self) -> float:
        return self.base_unit_cost + self.additional_unit_cost


@dataclass
class PaymentOption:
    label: str
    value: str


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
    invoice_slogan: str = ""
    invoice_street: str = ""
    invoice_city: str = ""
    invoice_state: str = ""
    invoice_zip: str = ""
    invoice_phone: str = ""
    invoice_fax: str = ""
    invoice_terms: str = "Due on receipt"
    invoice_comments: str = ""
    invoice_contact_name: str = ""
    invoice_contact_phone: str = ""
    invoice_contact_email: str = ""
    payment_options: List[PaymentOption] = field(default_factory=list)
    payment_other: str = ""
    tax_rate_percent: float = 0.0
    tax_show_on_invoice: bool = False
    tax_add_to_total: bool = False
    cloud_sync_enabled: bool = False
    cloud_sync_provider: str = ""
    cloud_sync_interval_minutes: int = 5
    cloud_sync_config: Dict[str, str] = field(default_factory=dict)


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


@dataclass
class Vendor:
    id: Optional[int]
    name: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    account_number: str = ""
    notes: str = ""
    preferred_payment_method: str = ""


@dataclass
class Material:
    id: Optional[int]
    sku: str
    name: str
    category: str = ""
    description: str = ""
    unit_of_measure: str = ""
    quantity_on_hand: float = 0.0
    reorder_point: float = 0.0
    cost_per_unit: float = 0.0
    vendor_id: Optional[int] = None
    last_restocked: Optional[date] = None
    notes: str = ""
    lead_time_days: int = 0
    archived: bool = False

    @property
    def inventory_value(self) -> float:
        return self.quantity_on_hand * self.cost_per_unit


@dataclass
class MaterialTransaction:
    id: Optional[int]
    material_id: int
    transaction_date: datetime
    quantity_delta: float
    unit_cost: float = 0.0
    reason: str = ""
    reference_type: str = ""
    reference_id: Optional[int] = None
    created_by: str = ""
    notes: str = ""


@dataclass
class LossRecord:
    id: Optional[int]
    amount: float
    loss_date: date
    category: str
    description: str = ""
    details: str = ""
    is_product_loss: bool = False
    recorded_by: str = ""
    quantity: float = 0.0
    unit: str = ""
    order_id: Optional[int] = None
    order_item_id: Optional[int] = None
    product_id: Optional[int] = None
    material_id: Optional[int] = None
    product_name: str = ""
    material_name: str = ""


@dataclass
class RecurringExpense:
    id: Optional[int]
    category: str
    amount: float
    frequency: str
    start_date: Optional[date]
    end_date: Optional[date] = None
    day_of_month: Optional[int] = None
    next_occurrence: Optional[date] = None
    auto_record: bool = False
    notes: str = ""
    vendor_id: Optional[int] = None


@dataclass
class Expense:
    id: Optional[int]
    category: str
    amount: float
    expense_date: date
    description: str = ""
    payment_method: str = ""
    vendor_id: Optional[int] = None
    is_recurring: bool = False
    recurring_id: Optional[int] = None
    document_id: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class CRMContact:
    id: Optional[int]
    customer_name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    last_contacted: Optional[date] = None
    next_follow_up: Optional[date] = None
    preferred_channel: str = ""
    notes: str = ""


@dataclass
class CRMInteraction:
    id: Optional[int]
    contact_id: int
    interaction_date: datetime
    channel: str = ""
    summary: str = ""
    follow_up_date: Optional[date] = None
    follow_up_action: str = ""
    order_id: Optional[int] = None


@dataclass
class DocumentRecord:
    id: Optional[int]
    entity_type: str
    entity_id: Optional[int]
    file_path: str
    category: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    stored_at: str = ""
    checksum: str = ""
    created_at: Optional[datetime] = None


@dataclass
class GoalCheckpoint:
    id: Optional[int]
    goal_id: int
    checkpoint_date: date
    actual_value: float
    forecast_value: float = 0.0
    notes: str = ""


@dataclass
class BusinessGoal:
    id: Optional[int]
    name: str
    metric_type: str
    target_value: float
    start_date: Optional[date]
    end_date: Optional[date]
    current_value: float = 0.0
    owner: str = ""
    progress_notes: str = ""
    threshold_warning: float = 0.0
    threshold_critical: float = 0.0
    auto_calculate: bool = True
    checkpoints: List[GoalCheckpoint] = field(default_factory=list)

    @property
    def progress_ratio(self) -> float:
        if self.target_value == 0:
            return 0.0
        return max(0.0, min(1.0, self.current_value / self.target_value))

    @property
    def status(self) -> str:
        ratio = self.progress_ratio
        if ratio >= 1.0:
            return "complete"
        warning_threshold = self.threshold_warning or 0.0
        critical_threshold = self.threshold_critical or 0.0
        if ratio < critical_threshold:
            return "critical"
        if ratio < warning_threshold:
            return "warning"
        return "on-track"
