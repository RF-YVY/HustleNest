from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from ..data import expense_repository, loss_repository, order_repository
from ..data.database import create_connection
from . import bookkeeping_service
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
    return sum(loss.amount for loss in bookkeeping_service.operating_losses(losses))


def calculate_expense_total(*, start_date: Optional[date] = None, end_date: Optional[date] = None) -> float:
    expenses = expense_repository.list_expenses(start_date=start_date, end_date=end_date)
    return sum(expense.amount for expense in bookkeeping_service.operating_expenses(expenses))


def summarize_cash_flow(window_days: int = 30) -> CashFlowSummary:
    today = date.today()
    start_window = today - timedelta(days=window_days)

    # Only explicit dated book receipts are realized cash. Legacy order flags have no reliable payment date.
    books = bookkeeping_service.workspace(start_window, today)
    sales_realized = sum(float(entry["amount"]) for entry in books["entries"] if entry["is_bank"] and (entry["kind"] in {"receipt", "refund"} or entry["original_kind"] in {"receipt", "refund"}))
    receivables = 0.0
    for order in order_repository.fetch_order_report(None, today):
        actual = order_repository.fetch_order(order.order_id)
        if actual is None or actual.is_paid:
            continue
        with create_connection() as connection:
            workflow = connection.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?', (order.order_id,)).fetchone()
            posted = connection.execute("""SELECT COALESCE(SUM(-e.cents),0) AS paid
                FROM book_entries e JOIN book_transactions t ON t.id=e.transaction_id JOIN book_accounts a ON a.id=e.account_id
                WHERE t.order_id=? AND a.code IN ('sales','refunds','tax') AND (t.kind IN ('receipt','refund') OR (SELECT kind FROM book_transactions original WHERE original.id=t.reversed_id) IN ('receipt','refund'))""", (order.order_id,)).fetchone()
        posted_paid = float(posted['paid']) / 100
        paid = max(float(workflow["amount_paid"]) if workflow else 0.0, posted_paid)
        receivables += max(0.0, actual.display_total - paid)
    expenses_paid = -sum(float(entry["amount"]) for entry in books["entries"] if entry["is_bank"] and (entry["kind"] in {"expense", "fee", "inventory_purchase", "equipment_purchase"} or entry["original_kind"] in {"expense", "fee", "inventory_purchase", "equipment_purchase"}))
    losses_recorded = 0.0  # A noncash write-off is not another cash payment.
    recurring_upcoming = _sum_upcoming_recurring(window_days)
    projected_tax = 0.0  # Tax movements are tracked explicitly in Books & Banking.

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
            COALESCE(SUM(total_amount), 0) AS total_value
        FROM orders
        WHERE UPPER(TRIM(status)) NOT IN ('CANCELLED', 'CANCELED', 'QUOTE', 'DRAFT')
          AND deleted_at IS NULL
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
        WHERE UPPER(TRIM(o.status)) NOT IN ('CANCELLED', 'CANCELED', 'QUOTE', 'DRAFT')
          AND o.deleted_at IS NULL
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
