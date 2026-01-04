# HustleNest

Current Version: **v1.0**

HustleNest is a desktop application written in Python (PySide6) for tracking product orders, shipping progress, and sales performance. Data is stored locally in a SQLite database that is provisioned automatically on first launch. The interface provides a dashboard, streamlined order entry, detailed reporting, inventory forecasting, and in-app notifications for low stock and overdue orders.

## Features

- **Dashboard overview** displaying total sales, outstanding order count, product-level sales totals, and pending shipments.
- **Order entry workflow** capturing customer information, shipping status, target completion dates, and flexible line items.
- **Notifications center** surfacing low-inventory warnings and overdue order reminders alongside dashboard metrics.
- **SQLite-backed storage** with automatic schema creation and pragmatic repository helpers for analytics queries.
- **Reports tab** offering optional date filters, shipment status, export to CSV, and product aggregation matching the dashboard details.
- **Forecasting analytics** projecting product demand based on recent sales trends.
- **About page** summarizing capabilities and surfacing update status on launch.

## Prerequisites

- Windows 10 or later (other OSes supported if PySide6 is available)
- Python 3.11 or newer
- pip for dependency installation

## Setup

1. Create and activate a virtual environment (recommended):
    ```powershell
    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```
2. Install dependencies:
    ```powershell
    pip install -r requirements.txt
    ```
3. Initialize the database and launch the application:
    ```powershell
    python -m cyberlablog.main
    ```

The first run creates `%LOCALAPPDATA%\HustleNest\hustlenest.db`. Remove that file to reset all data.

HustleNest checks for updates on startup by reaching the GitHub repository (`RF-YVY/Sales-Tracking`). If a newer tag or release exists, the app prompts with a download link.

## Building an Executable

To package HustleNest as a Windows executable named **HustleNest** with the bundled application icon:

```powershell
& .venv\Scripts\python.exe -m PyInstaller --name HustleNest --windowed --icon "WickerMadeSales.ico" --add-data "WickerMadeSales.ico;." cyberlablog\main.py
```

The compiled application is placed in `dist/HustleNest/HustleNest.exe`.

## Project Structure

```
.github/
cyberlablog/
   __init__.py
   main.py                # PySide6 application entrypoint
   data/
      database.py          # SQLite setup and helpers
      order_repository.py  # Order persistence and analytics queries
   models/
      order_models.py      # Dataclasses for orders, items, and reporting DTOs
   services/
      order_service.py     # Business logic shared across tabs
   ui/
      main_window.py       # Main window with dashboard, orders, and reports tabs
   viewmodels/
      table_models.py      # Generic table model for Qt views
requirements.txt
README.md
```

## Roadmap Ideas

- Support editing or canceling existing orders directly from the history tab.
- Provide PDF export options alongside CSV for external reporting.
- Integrate additional form validation and inline error indicators for numeric inputs.

## License

This project currently has no explicit license. Add one if you plan to distribute the application.
