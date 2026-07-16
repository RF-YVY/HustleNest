from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from ..models.order_models import BusinessGoal, GoalCheckpoint
from .database import create_connection

_DATE_FORMAT = "%Y-%m-%d"


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        return datetime.fromisoformat(value).date()


def _row_to_goal(row) -> BusinessGoal:
    return BusinessGoal(
        id=int(row["id"]),
        name=row["name"],
        metric_type=row["metric_type"],
        target_value=float(row["target_value"] or 0.0),
        start_date=_parse_date(row["start_date"]),
        end_date=_parse_date(row["end_date"]),
        current_value=float(row["current_value"] or 0.0),
        owner=row["owner"] or "",
        progress_notes=row["progress_notes"] or "",
        threshold_warning=float(row["threshold_warning"] or 0.0),
        threshold_critical=float(row["threshold_critical"] or 0.0),
        auto_calculate=bool(row["auto_calculate"]),
        checkpoints=[],
    )


def _row_to_checkpoint(row) -> GoalCheckpoint:
    return GoalCheckpoint(
        id=int(row["id"]),
        goal_id=int(row["goal_id"]),
        checkpoint_date=_parse_date(row["checkpoint_date"]),
        actual_value=float(row["actual_value"] or 0.0),
        forecast_value=float(row["forecast_value"] or 0.0),
        notes=row["notes"] or "",
    )


def list_goals(*, include_checkpoints: bool = True) -> List[BusinessGoal]:
    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                metric_type,
                target_value,
                start_date,
                end_date,
                current_value,
                owner,
                progress_notes,
                threshold_warning,
                threshold_critical,
                auto_calculate
            FROM business_goals
            ORDER BY COALESCE(end_date, start_date) ASC, id ASC
            """
        ).fetchall()

    goals = [_row_to_goal(row) for row in rows]

    if include_checkpoints and goals:
        goal_ids = [goal.id for goal in goals if goal.id is not None]
        if goal_ids:
            placeholders = ",".join("?" for _ in goal_ids)
            with create_connection() as connection:
                checkpoint_rows = connection.execute(
                    f"""
                    SELECT
                        id,
                        goal_id,
                        checkpoint_date,
                        actual_value,
                        forecast_value,
                        notes
                    FROM goal_checkpoints
                    WHERE goal_id IN ({placeholders})
                    ORDER BY checkpoint_date ASC, id ASC
                    """,
                    goal_ids,
                ).fetchall()
            checkpoints = [_row_to_checkpoint(row) for row in checkpoint_rows]
            checkpoints_by_goal: dict[int, List[GoalCheckpoint]] = {}
            for checkpoint in checkpoints:
                checkpoints_by_goal.setdefault(checkpoint.goal_id, []).append(checkpoint)
            for goal in goals:
                if goal.id is not None:
                    goal.checkpoints = checkpoints_by_goal.get(goal.id, [])

    return goals


def get_goal(goal_id: int, *, include_checkpoints: bool = True) -> Optional[BusinessGoal]:
    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                metric_type,
                target_value,
                start_date,
                end_date,
                current_value,
                owner,
                progress_notes,
                threshold_warning,
                threshold_critical,
                auto_calculate
            FROM business_goals
            WHERE id = ?
            LIMIT 1
            """,
            (int(goal_id),),
        ).fetchone()

    if row is None:
        return None

    goal = _row_to_goal(row)
    if include_checkpoints:
        goal.checkpoints = list_checkpoints(goal.id)
    return goal


def save_goal(goal: BusinessGoal) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if goal.id:
                cursor.execute(
                    """
                    UPDATE business_goals
                    SET
                        name = ?,
                        metric_type = ?,
                        target_value = ?,
                        start_date = ?,
                        end_date = ?,
                        current_value = ?,
                        owner = ?,
                        progress_notes = ?,
                        threshold_warning = ?,
                        threshold_critical = ?,
                        auto_calculate = ?
                    WHERE id = ?
                    """,
                    (
                        goal.name.strip(),
                        goal.metric_type.strip(),
                        float(goal.target_value),
                        goal.start_date.isoformat() if goal.start_date else None,
                        goal.end_date.isoformat() if goal.end_date else None,
                        float(goal.current_value),
                        goal.owner.strip(),
                        goal.progress_notes.strip(),
                        float(goal.threshold_warning),
                        float(goal.threshold_critical),
                        int(bool(goal.auto_calculate)),
                        int(goal.id),
                    ),
                )
                goal_id = int(goal.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO business_goals (
                        name,
                        metric_type,
                        target_value,
                        start_date,
                        end_date,
                        current_value,
                        owner,
                        progress_notes,
                        threshold_warning,
                        threshold_critical,
                        auto_calculate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        goal.name.strip(),
                        goal.metric_type.strip(),
                        float(goal.target_value),
                        goal.start_date.isoformat() if goal.start_date else None,
                        goal.end_date.isoformat() if goal.end_date else None,
                        float(goal.current_value),
                        goal.owner.strip(),
                        goal.progress_notes.strip(),
                        float(goal.threshold_warning),
                        float(goal.threshold_critical),
                        int(bool(goal.auto_calculate)),
                    ),
                )
                goal_id = int(cursor.lastrowid)
            connection.commit()
            return goal_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_goal(goal_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM business_goals WHERE id = ?", (int(goal_id),))
        connection.commit()


def list_checkpoints(goal_id: Optional[int] = None) -> List[GoalCheckpoint]:
    params: List[object] = []
    where_clause = ""
    if goal_id is not None:
        where_clause = "WHERE goal_id = ?"
        params.append(int(goal_id))

    query = f"""
        SELECT
            id,
            goal_id,
            checkpoint_date,
            actual_value,
            forecast_value,
            notes
        FROM goal_checkpoints
        {where_clause}
        ORDER BY checkpoint_date ASC, id ASC
    """

    with create_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_row_to_checkpoint(row) for row in rows]


def save_checkpoint(checkpoint: GoalCheckpoint) -> int:
    with create_connection() as connection:
        cursor = connection.cursor()
        try:
            if checkpoint.id:
                cursor.execute(
                    """
                    UPDATE goal_checkpoints
                    SET
                        goal_id = ?,
                        checkpoint_date = ?,
                        actual_value = ?,
                        forecast_value = ?,
                        notes = ?
                    WHERE id = ?
                    """,
                    (
                        int(checkpoint.goal_id),
                        checkpoint.checkpoint_date.isoformat(),
                        float(checkpoint.actual_value),
                        float(checkpoint.forecast_value),
                        checkpoint.notes.strip(),
                        int(checkpoint.id),
                    ),
                )
                checkpoint_id = int(checkpoint.id)
            else:
                cursor.execute(
                    """
                    INSERT INTO goal_checkpoints (
                        goal_id,
                        checkpoint_date,
                        actual_value,
                        forecast_value,
                        notes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(checkpoint.goal_id),
                        checkpoint.checkpoint_date.isoformat(),
                        float(checkpoint.actual_value),
                        float(checkpoint.forecast_value),
                        checkpoint.notes.strip(),
                    ),
                )
                checkpoint_id = int(cursor.lastrowid)
            connection.commit()
            return checkpoint_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def delete_checkpoint(checkpoint_id: int) -> None:
    with create_connection() as connection:
        connection.execute("DELETE FROM goal_checkpoints WHERE id = ?", (int(checkpoint_id),))
        connection.commit()
