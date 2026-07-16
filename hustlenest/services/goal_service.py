from __future__ import annotations

from datetime import date
from typing import List

from ..data import goal_repository
from ..data.database import create_connection
from ..models.order_models import BusinessGoal
from . import finance_service


def evaluate_goals() -> List[BusinessGoal]:
    goals = goal_repository.list_goals(include_checkpoints=True)
    today = date.today()
    for goal in goals:
        if not goal.auto_calculate:
            continue
        period_start = goal.start_date or today.replace(month=1, day=1)
        period_end = goal.end_date or today
        if period_end > today:
            period_end = today
        if period_end < period_start:
            period_end = period_start
        metric = goal.metric_type.strip().lower()
        goal.current_value = _calculate_metric(metric, period_start, period_end)
    return goals


def _calculate_metric(metric: str, start_date: date, end_date: date) -> float:
    if metric in {"revenue", "sales"}:
        return finance_service.calculate_sales_total(start_date, end_date)
    if metric == "profit":
        return finance_service.calculate_profit_total(start_date, end_date)
    if metric == "orders":
        return float(_count_orders(start_date, end_date))
    if metric == "expenses":
        return finance_service.calculate_expense_total(start_date=start_date, end_date=end_date)
    if metric == "losses":
        return finance_service.calculate_loss_total(start_date=start_date, end_date=end_date)
    if metric == "crm-followups":
        return float(_count_crm_interactions(start_date, end_date))
    return 0.0


def _count_orders(start_date: date, end_date: date) -> int:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS order_count
            FROM orders
            WHERE UPPER(status) <> 'CANCELLED'
              AND order_date >= ?
              AND order_date <= ?
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    return int(row["order_count"] or 0)


def _count_crm_interactions(start_date: date, end_date: date) -> int:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS interaction_count
            FROM crm_interactions
            WHERE interaction_date >= ?
              AND interaction_date <= ?
            """,
            (f"{start_date.isoformat()} 00:00:00", f"{end_date.isoformat()} 23:59:59"),
        ).fetchone()
    return int(row["interaction_count"] or 0)
