from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from ..data import expense_repository, loss_repository, order_repository
from ..data.database import create_connection
from ..models.order_models import OutstandingOrder


@dataclass
class CashFlowSummary:
    window_days: int
    sales_realized: float
    receivables: float
    expenses_paid: float
    losses_recorded: float
    recurring_upcoming: float
    projected_tax: float
    net_projection: float


def calculate_loss_total(*, start_date: Optional[date] = None, end_date: Optional[date] = None) -> float:
    losses = loss_repository.fetch_losses(start_date=start_date, end_date=end_date)
    return sum(loss.amount for loss in losses)


def calculate_expense_total(*, start_date: Optional[date] = None, end_date: Optional[date] = None) -> float:
    expenses = expense_repository.list_expenses(start_date=start_date, end_date=end_date)
    return sum(expense.amount for expense in expenses)


def summarize_cash_flow(window_days: int = 30) -> CashFlowSummary:
    today = date.today()
    start_window = today - timedelta(days=window_days)

    sales_realized = _fetch_sales_total(start_window, today)
    receivables = _sum_receivables(order_repository.fetch_outstanding_orders())
    expenses_paid = calculate_expense_total(start_date=start_window, end_date=today)
    losses_recorded = calculate_loss_total(start_date=start_window, end_date=today)
    recurring_upcoming = _sum_upcoming_recurring(window_days)
    projected_tax = order_repository.fetch_tax_total(start_window, today)

    net_projection = (
        sales_realized
        + receivables
        - expenses_paid
        - losses_recorded
        - recurring_upcoming
        - projected_tax
    )

    return CashFlowSummary(
        window_days=window_days,
        sales_realized=sales_realized,
        receivables=receivables,
        expenses_paid=expenses_paid,
        losses_recorded=losses_recorded,
        recurring_upcoming=recurring_upcoming,
        projected_tax=projected_tax,
        net_projection=net_projection,
    )


def _fetch_sales_total(start_date: date, end_date: date) -> float:
    query = """
        SELECT
            COALESCE(SUM(total_amount + tax_amount), 0) AS total_value
        FROM orders
        WHERE UPPER(status) <> 'CANCELLED'
          AND order_date >= ?
          AND order_date <= ?
    """
    with create_connection() as connection:
        row = connection.execute(
            query,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    return float(row["total_value"] or 0.0)


def calculate_sales_total(start_date: date, end_date: date) -> float:
    return _fetch_sales_total(start_date, end_date)


def calculate_profit_total(start_date: date, end_date: date) -> float:
    sales, cost = _fetch_sales_and_cost(start_date, end_date)
    return sales - cost


def calculate_cogs_total(start_date: date, end_date: date) -> float:
    """Calculate the total cost of goods sold within a date range."""
    _, cost = _fetch_sales_and_cost(start_date, end_date)
    return cost


def _sum_receivables(orders: Iterable[OutstandingOrder]) -> float:
    total = 0.0
    for order in orders:
        total += float(order.display_total)
    return total


def _sum_upcoming_recurring(window_days: int) -> float:
    upcoming_total = 0.0
    today = date.today()
    horizon = today + timedelta(days=window_days)
    for recurring in expense_repository.list_recurring_expenses():
        if recurring.next_occurrence is None:
            continue
        if recurring.next_occurrence < today:
            upcoming_total += float(recurring.amount)
        elif recurring.next_occurrence <= horizon:
            upcoming_total += float(recurring.amount)
    return upcoming_total


def _fetch_sales_and_cost(start_date: date, end_date: date) -> tuple[float, float]:
    query = """
        SELECT
            oi.quantity,
            oi.unit_price,
            oi.base_unit_cost,
            oi.cost_components
        FROM order_items AS oi
        JOIN orders AS o ON o.id = oi.order_id
        WHERE UPPER(o.status) <> 'CANCELLED'
          AND o.order_date >= ?
          AND o.order_date <= ?
    """
    total_sales = 0.0
    total_cost = 0.0
    with create_connection() as connection:
        cursor = connection.execute(query, (start_date.isoformat(), end_date.isoformat()))
        for row in cursor.fetchall():
            quantity = int(row["quantity"] or 0)
            unit_price = float(row["unit_price"] or 0.0)
            base_cost = float(row["base_unit_cost"] or 0.0)
            extras = _deserialize_cost_components(row["cost_components"])
            total_sales += quantity * unit_price
            total_cost += quantity * (base_cost + extras)
    return total_sales, total_cost


def _deserialize_cost_components(raw: object) -> float:
    import json

    if raw is None:
        return 0.0
    text = str(raw).strip()
    if not text:
        return 0.0
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return 0.0
    total = 0.0
    for entry in payload:
        try:
            total += float(entry.get("amount", 0))
        except (AttributeError, TypeError, ValueError):
            continue
    return total
