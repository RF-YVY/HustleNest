"""PDF report generation service."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..data import order_repository, product_repository, settings_repository
from ..services import finance_service, expense_service, loss_service
from ..models.order_models import (
    AppSettings,
    DashboardSnapshot,
    Order,
    OrderReportRow,
    Product,
    ProductSalesSummary,
    CustomerSalesSummary,
)


def _format_currency(amount: float) -> str:
    """Format a number as currency."""
    return f"${amount:,.2f}"


def _format_percent(value: float) -> str:
    """Format a number as a percentage."""
    return f"{value * 100:.1f}%"


def _get_period_dates(period: str) -> Tuple[date, date]:
    """
    Get start and end dates for a named period.
    
    Args:
        period: One of "this_month", "last_month", "this_quarter", "last_quarter",
                "this_year", "last_year", "last_30_days", "last_90_days"
    
    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()
    
    if period == "this_month":
        start = today.replace(day=1)
        end = today
    elif period == "last_month":
        first_of_this_month = today.replace(day=1)
        end = first_of_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "this_quarter":
        quarter = (today.month - 1) // 3
        start = date(today.year, quarter * 3 + 1, 1)
        end = today
    elif period == "last_quarter":
        quarter = (today.month - 1) // 3
        if quarter == 0:
            start = date(today.year - 1, 10, 1)
            end = date(today.year - 1, 12, 31)
        else:
            start = date(today.year, (quarter - 1) * 3 + 1, 1)
            end_month = quarter * 3
            if end_month == 3:
                end = date(today.year, 3, 31)
            elif end_month == 6:
                end = date(today.year, 6, 30)
            else:
                end = date(today.year, 9, 30)
    elif period == "this_year":
        start = date(today.year, 1, 1)
        end = today
    elif period == "last_year":
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)
    elif period == "last_30_days":
        start = today - timedelta(days=30)
        end = today
    elif period == "last_90_days":
        start = today - timedelta(days=90)
        end = today
    else:
        # Default to this month
        start = today.replace(day=1)
        end = today
    
    return start, end


def generate_sales_report_html(
    start_date: date,
    end_date: date,
    settings: AppSettings,
    include_details: bool = True,
) -> str:
    """
    Generate an HTML sales report.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        settings: Application settings
        include_details: Whether to include order details
    
    Returns:
        HTML string
    """
    # Get data
    orders = order_repository.list_orders_in_range(start_date, end_date)
    total_sales = sum(o.total_amount for o in orders)
    total_cost = sum(o.total_cost for o in orders)
    total_profit = total_sales - total_cost
    margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    
    paid_sales = sum(o.total_amount for o in orders if o.is_paid)
    unpaid_sales = sum(o.total_amount for o in orders if not o.is_paid)
    
    # Get product breakdown
    product_sales = order_repository.get_product_sales_summary(start_date, end_date)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sales Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            max-width: 100%;
            margin: 0;
            padding: 10px;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
            margin-bottom: 10px;
        }}
        h2 {{
            font-size: 16px;
            color: #444;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        .header {{
            margin-bottom: 10px;
        }}
        .period {{
            color: #666;
            font-size: 13px;
            margin-bottom: 15px;
        }}
        .summary-grid {{
            display: table;
            width: 100%;
            margin-bottom: 20px;
        }}
        .summary-card {{
            display: inline-block;
            width: 15%;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
            margin-right: 2%;
            vertical-align: top;
            box-sizing: border-box;
        }}
        .summary-card:last-child {{
            margin-right: 0;
        }}
        .summary-card .value {{
            font-size: 16px;
            font-weight: bold;
            color: #0078d4;
        }}
        .summary-card .label {{
            font-size: 11px;
            color: #555;
            margin-top: 4px;
            font-weight: 500;
        }}
        .summary-card .value.paid {{
            color: #107c10;
        }}
        .summary-card .value.unpaid {{
            color: #ca5010;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 12px;
        }}
        th, td {{
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f0f0f0;
            font-weight: bold;
            font-size: 12px;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .text-right {{
            text-align: right;
        }}
        .positive {{
            color: #107c10;
        }}
        .negative {{
            color: #d13438;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 11px;
            color: #666;
        }}
        @media print {{
            body {{
                padding: 0;
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{settings.business_name} - Sales Report</h1>
    </div>
    <p class="period">Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}</p>
    
    <div class="summary-grid">
        <div class="summary-card">
            <div class="value">{_format_currency(total_sales)}</div>
            <div class="label">Total Sales</div>
        </div>
        <div class="summary-card">
            <div class="value paid">{_format_currency(paid_sales)}</div>
            <div class="label">Paid</div>
        </div>
        <div class="summary-card">
            <div class="value unpaid">{_format_currency(unpaid_sales)}</div>
            <div class="label">Unpaid</div>
        </div>
        <div class="summary-card">
            <div class="value">{_format_currency(total_cost)}</div>
            <div class="label">Total Cost</div>
        </div>
        <div class="summary-card">
            <div class="value {'positive' if total_profit >= 0 else 'negative'}">{_format_currency(total_profit)}</div>
            <div class="label">Profit</div>
        </div>
        <div class="summary-card">
            <div class="value">{margin:.1f}%</div>
            <div class="label">Margin</div>
        </div>
    </div>
    
    <h2>Product Performance</h2>
    <table>
        <thead>
            <tr>
                <th>Product</th>
                <th class="text-right">Qty Sold</th>
                <th class="text-right">Revenue</th>
                <th class="text-right">Cost</th>
                <th class="text-right">Profit</th>
                <th class="text-right">Margin</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for product in product_sales[:20]:
        html += f"""
            <tr>
                <td>{product.product_name}</td>
                <td class="text-right">{product.total_quantity}</td>
                <td class="text-right">{_format_currency(product.total_sales)}</td>
                <td class="text-right">{_format_currency(product.total_cost)}</td>
                <td class="text-right {'positive' if product.total_profit >= 0 else 'negative'}">{_format_currency(product.total_profit)}</td>
                <td class="text-right">{product.margin * 100:.1f}%</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
"""
    
    if include_details:
        html += f"""
    <h2>Order Details ({len(orders)} orders)</h2>
    <table>
        <thead>
            <tr>
                <th>Order #</th>
                <th>Date</th>
                <th>Customer</th>
                <th>Status</th>
                <th class="text-right">Amount</th>
            </tr>
        </thead>
        <tbody>
"""
        for order in orders[:50]:
            html += f"""
            <tr>
                <td>{order.order_number}</td>
                <td>{order.order_date.strftime('%Y-%m-%d')}</td>
                <td>{order.customer_name}</td>
                <td>{order.status}</td>
                <td class="text-right">{_format_currency(order.total_amount)}</td>
            </tr>
"""
        
        if len(orders) > 50:
            html += f"""
            <tr>
                <td colspan="5" style="text-align: center; font-style: italic;">
                    ... and {len(orders) - 50} more orders
                </td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
"""
    
    html += f"""
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_inventory_report_html(settings: AppSettings) -> str:
    """
    Generate an HTML inventory report.
    
    Args:
        settings: Application settings
    
    Returns:
        HTML string
    """
    products = product_repository.list_products()
    
    # Sort by inventory count (low first)
    products.sort(key=lambda p: p.inventory_count)
    
    low_stock = [p for p in products if p.inventory_count <= settings.low_inventory_threshold]
    total_value = sum(p.inventory_count * p.base_unit_cost for p in products)
    total_retail = sum(p.inventory_count * p.default_unit_price for p in products)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Inventory Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            max-width: 100%;
            margin: 0;
            padding: 10px;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
        }}
        h2 {{
            font-size: 16px;
            color: #444;
            margin-top: 20px;
        }}
        p {{
            font-size: 13px;
        }}
        .summary-grid {{
            display: table;
            width: 100%;
            margin-bottom: 20px;
        }}
        .summary-card {{
            display: inline-block;
            width: 23%;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
            margin-right: 2%;
            vertical-align: top;
            box-sizing: border-box;
        }}
        .summary-card:last-child {{
            margin-right: 0;
        }}
        .summary-card .value {{
            font-size: 18px;
            font-weight: bold;
            color: #0078d4;
        }}
        .summary-card .label {{
            font-size: 11px;
            color: #555;
            margin-top: 4px;
            font-weight: 500;
        }}
        .alert {{
            background: #fff4ce;
            border-left: 4px solid #ffb900;
            padding: 10px 15px;
            margin-bottom: 15px;
            font-size: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 12px;
        }}
        th, td {{
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f0f0f0;
            font-weight: bold;
            font-size: 12px;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .text-right {{
            text-align: right;
        }}
        .low-stock {{
            color: #d13438;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 11px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>{settings.business_name} - Inventory Report</h1>
    <p>Generated: {datetime.now().strftime('%B %d, %Y')}</p>
    
    <div class="summary-grid">
        <div class="summary-card">
            <div class="value">{len(products)}</div>
            <div class="label">Total Products</div>
        </div>
        <div class="summary-card">
            <div class="value">{sum(p.inventory_count for p in products)}</div>
            <div class="label">Total Units</div>
        </div>
        <div class="summary-card">
            <div class="value">{_format_currency(total_value)}</div>
            <div class="label">Inventory Value (Cost)</div>
        </div>
        <div class="summary-card">
            <div class="value">{_format_currency(total_retail)}</div>
            <div class="label">Retail Value</div>
        </div>
    </div>
"""
    
    if low_stock:
        html += f"""
    <div class="alert">
        <strong>⚠️ Low Stock Alert:</strong> {len(low_stock)} product(s) at or below reorder threshold ({settings.low_inventory_threshold} units)
    </div>
"""
    
    html += """
    <h2>Full Inventory</h2>
    <table>
        <thead>
            <tr>
                <th>SKU</th>
                <th>Product Name</th>
                <th>Status</th>
                <th class="text-right">In Stock</th>
                <th class="text-right">Unit Cost</th>
                <th class="text-right">Unit Price</th>
                <th class="text-right">Value</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for product in products:
        is_low = product.inventory_count <= settings.low_inventory_threshold
        stock_class = "low-stock" if is_low else ""
        value = product.inventory_count * product.base_unit_cost
        
        html += f"""
            <tr>
                <td>{product.sku}</td>
                <td>{product.name}</td>
                <td>{product.status}</td>
                <td class="text-right {stock_class}">{product.inventory_count}</td>
                <td class="text-right">{_format_currency(product.base_unit_cost)}</td>
                <td class="text-right">{_format_currency(product.default_unit_price)}</td>
                <td class="text-right">{_format_currency(value)}</td>
            </tr>
"""
    
    html += f"""
        </tbody>
    </table>
    
    <div class="footer">
        <p>Low stock threshold: {settings.low_inventory_threshold} units</p>
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_pnl_report_html(
    start_date: date,
    end_date: date,
    settings: AppSettings,
) -> str:
    """
    Generate an HTML Profit & Loss statement.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        settings: Application settings
    
    Returns:
        HTML string
    """
    # Get financial data
    revenue = finance_service.calculate_sales_total(start_date, end_date)
    cogs = finance_service.calculate_cogs_total(start_date, end_date)
    gross_profit = revenue - cogs
    
    # Get paid/unpaid breakdown
    orders = order_repository.list_orders_in_range(start_date, end_date)
    paid_sales = sum(o.total_amount for o in orders if o.is_paid)
    unpaid_sales = sum(o.total_amount for o in orders if not o.is_paid)
    
    expenses = finance_service.calculate_expense_total(start_date=start_date, end_date=end_date)
    losses = finance_service.calculate_loss_total(start_date=start_date, end_date=end_date)
    
    operating_profit = gross_profit - expenses - losses
    
    # Get expense breakdown
    expense_breakdown = expense_service.get_expense_breakdown(start_date, end_date)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Profit & Loss Statement</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            max-width: 100%;
            margin: 0;
            padding: 10px;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            color: #0078d4;
            text-align: center;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
        }}
        h2 {{
            font-size: 16px;
        }}
        .period {{
            text-align: center;
            color: #666;
            font-size: 13px;
            margin-bottom: 20px;
        }}
        .section {{
            margin-bottom: 15px;
        }}
        .section-title {{
            font-weight: bold;
            font-size: 12px;
            color: #555;
            text-transform: uppercase;
            margin-bottom: 8px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 4px;
        }}
        .line-item {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 12px;
        }}
        .line-item.indent {{
            padding-left: 15px;
        }}
        .line-item.total {{
            font-weight: bold;
            font-size: 13px;
            border-top: 2px solid #ddd;
            border-bottom: none;
            margin-top: 8px;
            padding-top: 8px;
        }}
        .line-item.grand-total {{
            font-size: 16px;
            background: #f5f5f5;
            padding: 12px;
            margin-top: 15px;
            border-radius: 6px;
        }}
        .positive {{
            color: #107c10;
        }}
        .negative {{
            color: #d13438;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 11px;
            color: #666;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>{settings.business_name}</h1>
    <h2 style="text-align: center; margin-top: -10px;">Profit & Loss Statement</h2>
    <p class="period">{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}</p>
    
    <div class="section">
        <div class="section-title">Revenue</div>
        <div class="line-item">
            <span>Sales Revenue</span>
            <span>{_format_currency(revenue)}</span>
        </div>
        <div class="line-item indent" style="color: #107c10;">
            <span>Paid</span>
            <span>{_format_currency(paid_sales)}</span>
        </div>
        <div class="line-item indent" style="color: #ca5010;">
            <span>Unpaid</span>
            <span>{_format_currency(unpaid_sales)}</span>
        </div>
        <div class="line-item total">
            <span>Total Revenue</span>
            <span>{_format_currency(revenue)}</span>
        </div>
    </div>
    
    <div class="section">
        <div class="section-title">Cost of Goods Sold</div>
        <div class="line-item">
            <span>Product Costs</span>
            <span>{_format_currency(cogs)}</span>
        </div>
        <div class="line-item total">
            <span>Total COGS</span>
            <span>{_format_currency(cogs)}</span>
        </div>
    </div>
    
    <div class="line-item total" style="font-size: 18px;">
        <span>Gross Profit</span>
        <span class="{'positive' if gross_profit >= 0 else 'negative'}">{_format_currency(gross_profit)}</span>
    </div>
    <div class="line-item" style="font-size: 15px; color: #666;">
        <span>Gross Margin</span>
        <span>{(gross_profit / revenue * 100) if revenue > 0 else 0:.1f}%</span>
    </div>
    
    <div class="section" style="margin-top: 30px;">
        <div class="section-title">Operating Expenses</div>
"""
    
    for category, amount in expense_breakdown.items():
        html += f"""
        <div class="line-item indent">
            <span>{category}</span>
            <span>{_format_currency(amount)}</span>
        </div>
"""
    
    html += f"""
        <div class="line-item total">
            <span>Total Expenses</span>
            <span>{_format_currency(expenses)}</span>
        </div>
    </div>
"""
    
    if losses > 0:
        html += f"""
    <div class="section">
        <div class="section-title">Losses & Write-offs</div>
        <div class="line-item">
            <span>Total Losses</span>
            <span class="negative">{_format_currency(losses)}</span>
        </div>
    </div>
"""
    
    html += f"""
    <div class="line-item grand-total">
        <span>Net Operating Profit</span>
        <span class="{'positive' if operating_profit >= 0 else 'negative'}">{_format_currency(operating_profit)}</span>
    </div>
    
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_customer_report_html(
    start_date: date,
    end_date: date,
    settings: AppSettings,
) -> str:
    """
    Generate an HTML customer sales report.
    
    Args:
        start_date: Report start date
        end_date: Report end date
        settings: Application settings
    
    Returns:
        HTML string
    """
    customers = order_repository.get_customer_sales_summary(start_date, end_date)
    
    # Sort by total sales
    customers.sort(key=lambda c: c.total_sales, reverse=True)
    
    total_revenue = sum(c.total_sales for c in customers)
    total_orders = sum(c.order_count for c in customers)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Customer Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            max-width: 100%;
            margin: 0;
            padding: 10px;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
        }}
        h2 {{
            font-size: 16px;
        }}
        .period {{
            color: #666;
            font-size: 13px;
            margin-bottom: 15px;
        }}
        .summary-grid {{
            display: table;
            width: 100%;
            margin-bottom: 20px;
        }}
        .summary-card {{
            display: inline-block;
            width: 31%;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
            margin-right: 2%;
            vertical-align: top;
            box-sizing: border-box;
        }}
        .summary-card:last-child {{
            margin-right: 0;
        }}
        .summary-card .value {{
            font-size: 18px;
            font-weight: bold;
            color: #0078d4;
        }}
        .summary-card .label {{
            font-size: 11px;
            color: #555;
            margin-top: 4px;
            font-weight: 500;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 12px;
        }}
        th, td {{
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f0f0f0;
            font-weight: bold;
            font-size: 12px;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .text-right {{
            text-align: right;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 11px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>{settings.business_name} - Customer Report</h1>
    <p class="period">Period: {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}</p>
    
    <div class="summary-grid">
        <div class="summary-card">
            <div class="value">{len(customers)}</div>
            <div class="label">Total Customers</div>
        </div>
        <div class="summary-card">
            <div class="value">{total_orders}</div>
            <div class="label">Total Orders</div>
        </div>
        <div class="summary-card">
            <div class="value">{_format_currency(total_revenue)}</div>
            <div class="label">Total Revenue</div>
        </div>
    </div>
    
    <h2>Customer Sales Ranking</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Customer</th>
                <th class="text-right">Orders</th>
                <th class="text-right">Total Sales</th>
                <th class="text-right">Avg Order</th>
                <th class="text-right">% of Revenue</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for i, customer in enumerate(customers[:50], start=1):
        pct = (customer.total_sales / total_revenue * 100) if total_revenue > 0 else 0
        html += f"""
            <tr>
                <td>{i}</td>
                <td>{customer.customer_name}</td>
                <td class="text-right">{customer.order_count}</td>
                <td class="text-right">{_format_currency(customer.total_sales)}</td>
                <td class="text-right">{_format_currency(customer.average_order)}</td>
                <td class="text-right">{pct:.1f}%</td>
            </tr>
"""
    
    html += f"""
        </tbody>
    </table>
    
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_comparison_report_html(
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
    period1_label: str,
    period2_label: str,
    settings: AppSettings,
) -> str:
    """
    Generate an HTML comparison report between two periods.
    
    Args:
        period1_start, period1_end: First period dates
        period2_start, period2_end: Second period dates
        period1_label, period2_label: Labels for the periods
        settings: Application settings
    
    Returns:
        HTML string
    """
    # Get period 1 data
    p1_revenue = finance_service.calculate_sales_total(period1_start, period1_end)
    p1_cost = finance_service.calculate_cogs_total(period1_start, period1_end)
    p1_profit = p1_revenue - p1_cost
    p1_expenses = finance_service.calculate_expense_total(start_date=period1_start, end_date=period1_end)
    p1_orders = order_repository.count_orders_in_range(period1_start, period1_end)
    
    # Get period 2 data
    p2_revenue = finance_service.calculate_sales_total(period2_start, period2_end)
    p2_cost = finance_service.calculate_cogs_total(period2_start, period2_end)
    p2_profit = p2_revenue - p2_cost
    p2_expenses = finance_service.calculate_expense_total(start_date=period2_start, end_date=period2_end)
    p2_orders = order_repository.count_orders_in_range(period2_start, period2_end)
    
    def calc_change(current: float, previous: float) -> Tuple[float, str]:
        if previous == 0:
            if current == 0:
                return 0.0, "0%"
            return 100.0, "+100%"
        change = ((current - previous) / abs(previous)) * 100
        sign = "+" if change > 0 else ""
        return change, f"{sign}{change:.1f}%"
    
    rev_change, rev_change_str = calc_change(p1_revenue, p2_revenue)
    profit_change, profit_change_str = calc_change(p1_profit, p2_profit)
    order_change, order_change_str = calc_change(p1_orders, p2_orders)
    expense_change, expense_change_str = calc_change(p1_expenses, p2_expenses)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Period Comparison Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 13px;
            line-height: 1.4;
            max-width: 100%;
            margin: 0;
            padding: 10px;
            color: #333;
        }}
        h1 {{
            font-size: 20px;
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 8px;
        }}
        p {{
            font-size: 13px;
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 12px;
        }}
        .comparison-table th, .comparison-table td {{
            padding: 8px 10px;
            text-align: right;
            border-bottom: 1px solid #ddd;
        }}
        .comparison-table th:first-child, .comparison-table td:first-child {{
            text-align: left;
            font-weight: bold;
        }}
        .comparison-table thead th {{
            background: #f0f0f0;
            font-size: 12px;
        }}
        .positive {{
            color: #107c10;
        }}
        .negative {{
            color: #d13438;
        }}
        .change-cell {{
            font-weight: bold;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            font-size: 11px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>{settings.business_name} - Period Comparison</h1>
    <p>Comparing <strong>{period1_label}</strong> vs <strong>{period2_label}</strong></p>
    
    <table class="comparison-table">
        <thead>
            <tr>
                <th>Metric</th>
                <th>{period1_label}</th>
                <th>{period2_label}</th>
                <th>Change</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Revenue</td>
                <td>{_format_currency(p1_revenue)}</td>
                <td>{_format_currency(p2_revenue)}</td>
                <td class="change-cell {'positive' if rev_change >= 0 else 'negative'}">{rev_change_str}</td>
            </tr>
            <tr>
                <td>Cost of Goods</td>
                <td>{_format_currency(p1_cost)}</td>
                <td>{_format_currency(p2_cost)}</td>
                <td class="change-cell">{calc_change(p1_cost, p2_cost)[1]}</td>
            </tr>
            <tr>
                <td>Gross Profit</td>
                <td>{_format_currency(p1_profit)}</td>
                <td>{_format_currency(p2_profit)}</td>
                <td class="change-cell {'positive' if profit_change >= 0 else 'negative'}">{profit_change_str}</td>
            </tr>
            <tr>
                <td>Expenses</td>
                <td>{_format_currency(p1_expenses)}</td>
                <td>{_format_currency(p2_expenses)}</td>
                <td class="change-cell {'negative' if expense_change > 0 else 'positive'}">{expense_change_str}</td>
            </tr>
            <tr>
                <td>Order Count</td>
                <td>{p1_orders}</td>
                <td>{p2_orders}</td>
                <td class="change-cell {'positive' if order_change >= 0 else 'negative'}">{order_change_str}</td>
            </tr>
            <tr>
                <td>Avg Order Value</td>
                <td>{_format_currency(p1_revenue / p1_orders if p1_orders > 0 else 0)}</td>
                <td>{_format_currency(p2_revenue / p2_orders if p2_orders > 0 else 0)}</td>
                <td class="change-cell">-</td>
            </tr>
        </tbody>
    </table>
    
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""
    
    return html
