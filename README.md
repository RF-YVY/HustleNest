# HustleNest

Version: **v2.0**

HustleNest is a PySide6 desktop application for tracking product orders, monitoring fulfillment, and visualizing sales performance. All data lives locally in a SQLite database created automatically on first launch. The UI combines dashboards, detailed order entry, forecasting, and reporting tailored for small business workflows.

## Highlights

- Dashboard with revenue, order pipeline, and inventory insights.
- Order management with product line items, paid-status toggle, and invoice export.
- Local SQLite storage with repository helpers for analytics and reporting.
- Configurable payment methods and branded invoice PDFs generated in-app.
- Built-in update checker pointed at the HustleNest GitHub repository.

## What's New in 2.0

- Windows installer built with Inno Setup for a streamlined deployment story.
- PyInstaller bundle refreshed with the HustleNest branding and icon.
- Invoice manager now supports dynamic payment methods, persistent settings, and a compact layout with totals embedded in the items table.
- Paid checkbox in the Orders tab syncs with database state without mutating order status.
- Cost and margin analytics surfaced across dashboards, reports, and exports.

## Dashboard
<img width="1602" height="1064" alt="Image" src="https://github.com/user-attachments/assets/ac916871-8087-4669-af9e-38a1ccc831f7" />

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

MIT License

Copyright (c) 2026 Brett Wicker
https://bio.link/k5yvy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contact:
For questions/suggestions/etc email: kd5yvy@gmail.com



