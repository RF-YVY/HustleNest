# HustleNest

Current Version: **v1.1** **(Download EXE from Releases, no installation needed)**

HustleNest is a desktop application written in Python (PySide6) for tracking product orders, shipping progress, and sales performance. Data is stored locally in a SQLite database that is provisioned automatically on first launch. The interface provides a dashboard, streamlined order entry, detailed reporting, inventory forecasting, and in-app notifications for low stock and overdue orders.

## Features

- **Dashboard overview** displaying total sales, outstanding order count, product-level sales totals, and pending shipments.
- **Order entry workflow** capturing customer information, shipping status, target completion dates, and flexible line items.
- **Notifications center** surfacing low-inventory warnings and overdue order reminders alongside dashboard metrics.
- **SQLite-backed storage** with automatic schema creation and pragmatic repository helpers for analytics queries.
- **Reports tab** offering optional date filters, shipment status, export to CSV, and product aggregation matching the dashboard details.
- **Forecasting analytics** projecting product demand based on recent sales trends.
- **About page** summarizing capabilities and surfacing update status on launch.

## Dashboard
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/d2930b53-abe5-4bb3-a905-2c741db14829" />

## Orders
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/08a66791-85a1-4c13-a4cd-bc4bdec6a942" />

## Reports
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/f156e5b4-644d-4c9a-b859-9f9247bbd810" />

## History
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/77d488bf-95a9-4c44-81f6-31b7f9fe83f2" />

## Product Manager
<img width="1602" height="1062" alt="Image" src="https://github.com/user-attachments/assets/43a38ea2-8158-4e20-9c2e-31d9c23eb2e4" />

## Graphs
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/e6069990-6873-4755-92bf-da67abb9ff32" />

## Mapping
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/a1e048b3-af56-4827-a76f-10184aeac569" />

## Settings
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/9e9e3903-c6d8-45b1-8306-c0ea3826932e" />

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

HustleNest checks for updates on startup by reaching the GitHub repository (`RF-YVY/HustleNest`). If a newer tag or release exists, the app prompts with a download link.

## Building an Executable

To package HustleNest as a Windows executable named **HustleNest** with the bundled application icon:

```powershell
& .venv\Scripts\python.exe -m PyInstaller --name HustleNest --windowed --icon "HustleNest.ico" --add-data "HustleNest.ico;." cyberlablog\main.py
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

