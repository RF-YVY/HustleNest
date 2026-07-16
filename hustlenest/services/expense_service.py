from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional

from ..data import expense_repository
from ..models.order_models import Expense, RecurringExpense


def list_expenses(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[Iterable[str]] = None,
    vendor_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Expense]:
    return expense_repository.list_expenses(
        start_date=start_date,
        end_date=end_date,
        categories=categories,
        vendor_id=vendor_id,
        limit=limit,
    )


def save_expense(expense: Expense) -> int:
    return expense_repository.save_expense(expense)


def delete_expense(expense_id: int) -> None:
    expense_repository.delete_expense(expense_id)


def list_categories(*, include_recurring: bool = True) -> List[str]:
    return expense_repository.list_categories(include_recurring=include_recurring)


def list_recurring_expenses() -> List[RecurringExpense]:
    return expense_repository.list_recurring_expenses()


def save_recurring_expense(recurring: RecurringExpense) -> int:
    return expense_repository.save_recurring_expense(recurring)


def delete_recurring_expense(recurring_id: int) -> None:
    expense_repository.delete_recurring_expense(recurring_id)


def summarize_by_category(
    *, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Dict[str, float]:
    summary: Dict[str, float] = defaultdict(float)
    for expense in list_expenses(start_date=start_date, end_date=end_date):
        summary[expense.category] += float(expense.amount)
    return dict(summary)


def get_expense_breakdown(start_date: date, end_date: date) -> Dict[str, float]:
    """Get expense breakdown by category for a date range."""
    return summarize_by_category(start_date=start_date, end_date=end_date)
