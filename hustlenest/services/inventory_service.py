from __future__ import annotations

from dataclasses import replace
from typing import List

from ..data import material_repository, order_repository, settings_repository
from ..models.order_models import Material, NotificationMessage, ProductForecast


def calculate_materials_value(*, include_archived: bool = False) -> float:
    materials = material_repository.list_materials(include_archived=include_archived)
    return sum(material.inventory_value for material in materials)


def build_inventory_alerts(window_days: int = 30, limit: int = 50) -> List[NotificationMessage]:
    settings = settings_repository.get_app_settings()
    threshold = settings.low_inventory_threshold
    alerts: List[NotificationMessage] = []

    forecasts = order_repository.fetch_product_forecast(window_days, limit)
    for forecast in forecasts:
        needs_reorder = forecast.inventory_count <= threshold
        if forecast.days_until_stockout is not None and forecast.days_until_stockout <= 21:
            needs_reorder = True
        if not needs_reorder:
            continue
        normalized = replace(forecast, needs_reorder=True)
        alerts.append(_format_product_alert(normalized))

    for material in material_repository.list_materials(include_archived=False):
        if material.archived:
            continue
        if material.quantity_on_hand <= material.reorder_point:
            alerts.append(_format_material_alert(material))

    return alerts


def _format_product_alert(forecast: ProductForecast) -> NotificationMessage:
    if forecast.days_until_stockout is None:
        suffix = " (insufficient sales history)"
    else:
        suffix = f", est. {forecast.days_until_stockout} day(s) remaining"
    message = (
        f"Product inventory low for {forecast.sku} - {forecast.name}: "
        f"{forecast.inventory_count} units on hand{suffix}."
    )
    return NotificationMessage("Inventory", message, "warning")


def _format_material_alert(material: Material) -> NotificationMessage:
    message = (
        f"Material '{material.name}' below threshold: "
        f"{material.quantity_on_hand:g} {material.unit_of_measure or 'units'} on hand, "
        f"reorder point {material.reorder_point:g}."
    )
    return NotificationMessage("Material", message, "warning")
