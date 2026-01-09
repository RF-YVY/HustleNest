# HustleNest

Version: **v2.1.1**

HustleNest is a PySide6 desktop application for tracking product orders, monitoring fulfillment, and visualizing sales performance. All data lives locally in a SQLite database created automatically on first launch. The UI combines dashboards, detailed order entry, forecasting, and reporting tailored for small business workflows.

## Highlights

- Dashboard with revenue, order pipeline, and inventory insights.
- Order management with product line items, paid-status toggle, and invoice export.
- Local SQLite storage with repository helpers for analytics and reporting.
- Configurable payment methods and branded invoice PDFs generated in-app.
- Built-in update checker pointed at the HustleNest GitHub repository.

## What's New in 2.1.1

- Saving an updated order now clears the selection so the entry form is ready for the next record immediately.
- Product selection, quantity, and pricing controls on the Orders tab now include inline labels and tooltips for quicker orientation.
- Exported invoices omit the placeholder comments block so PDFs only show content you provide.

## Installation

### Option 1: Windows Installer (recommended)

1. Download `HustleNestSetup.exe` from the latest release (or use the build/HustleNestSetup.exe artifact when building locally).
2. Run the installer and follow the prompts. The default location is `C:\Program Files\HustleNest`.
3. Launch HustleNest from the Start menu or the optional desktop shortcut.

### Option 2: Run from source

Windows 10 or later with Python 3.11 is required.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m cyberlablog.main
```

On first run a database file appears at `%LOCALAPPDATA%\HustleNest\hustlenest.db`. Deleting that file resets all application data.

## Running the App

- Installer build: launch HustleNest from Start > HustleNest > HustleNest.
- Source build: run `python -m cyberlablog.main` from an activated virtual environment.

Invoices export as PDFs through the Invoice Manager dialog, which launches when you select an order and choose **Export Invoice**.

## Building From Source

To recreate the distributable artifacts:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller HustleNest.spec
"C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" installer\HustleNest.iss
```

The PyInstaller step emits the executable in `dist\HustleNest\HustleNest.exe`. The Inno Setup compiler produces `build\HustleNestSetup.exe`.

## Project Structure

```
.github/
cyberlablog/
   __init__.py
   main.py                # PySide6 application entry point
   data/
      database.py         # SQLite bootstrap and helpers
      order_repository.py # Persistence and reporting queries
   models/
      order_models.py     # Dataclasses for orders, items, and invoice metadata
   services/
      order_service.py    # Business logic for invoices and analytics
   settings/
      app_settings.py     # Persistent application settings (payment methods, etc.)
   ui/
      main_window.py      # Main window with dashboard, orders, reports
   versioning.py          # Centralized application version constant
installer/
   HustleNest.iss         # Inno Setup script
requirements.txt
README.md
```

## Troubleshooting

- If the installer reports missing prerequisites, ensure the Visual C++ redistributables are present (PySide6 bundles the required runtime in the installer build).
- When running from source, verify the virtual environment is active before installing dependencies or launching the app.
- Delete `%LOCALAPPDATA%\HustleNest\hustlenest.db` if you need a clean slate for testing.

## License

This project currently has no explicit license. Add one if you plan to distribute the application.
