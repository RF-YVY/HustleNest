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
  
<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/3fadba1e-733b-46e1-bc80-f0ad7e17914d" />

<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/2d9ab96b-6f74-4861-980b-5470b6a29b6e" />

<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/c2523e58-a7c2-4ee2-943a-cc58f51fac8a" />

<img width="1813" height="1067" alt="Image" src="https://github.com/user-attachments/assets/51c3546a-c835-488a-9622-8ee59d72d2ed" />

<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/b1935985-ffda-4229-b081-4dbfdd4503f0" />

<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/67a33f89-422e-4d22-9660-a66ea0a85be1" />

<img width="1902" height="1122" alt="Image" src="https://github.com/user-attachments/assets/d3a57fd2-f363-4a37-a70e-183ce2ae0a84" />

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

