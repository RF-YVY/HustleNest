# HustleNest

Version: **v2.2.0**

HustleNest is a PySide6 desktop application for tracking product orders, monitoring fulfillment, and visualizing sales performance. All data lives locally in a SQLite database created automatically on first launch. The UI combines dashboards, detailed order entry, forecasting, and reporting tailored for small business workflows.

## Highlights

- Dashboard with revenue, order pipeline, and inventory insights.
- Order management with product line items, paid-status toggle, and invoice export.
- Local SQLite storage with repository helpers for analytics and reporting.
- Configurable payment methods and branded invoice PDFs generated in-app.
- Built-in update checker pointed at the HustleNest GitHub repository.

## What's New in 2.2.0

- Losses and expenses tabs now share the material categories dropdown for consistent tagging across business tools.
- Reports tab includes quarterly and year-end sales tax summaries with one-click CSV or PDF exports using the configured tax rate.
- CRM tab can import contacts from historical orders in one step to seed outreach efforts.

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

## Cloud Sync (Optional)

HustleNest can mirror its local SQLite database to a shared folder, personal Google Drive, Dropbox, Microsoft OneDrive, or a self-hosted SFTP destination. Open **Settings › Open Cloud Sync Settings…** to enable the feature:

- Enable periodic cloud sync, choose a provider, and set the interval (default five minutes).
- **Local Folder (sync client)**: Pick a directory (for example `C:\\Users\\<you>\\Documents\\HustleNestDB`) that is kept in sync by another tool such as Google Drive, OneDrive, Dropbox, or a network share. Set an optional remote file name if you do not want to use the default `hustlenest.db`.
- **Personal Google Drive**: Provide the OAuth client secrets JSON, run **Authorize Google Drive** to generate a token JSON, and optionally set the Drive folder ID and remote file name.
- **Dropbox**: Supply a long-lived access token and the remote path (for example `/Apps/HustleNest/hustlenest.db`).
- **Microsoft OneDrive**: Enter the MSAL application client ID, client secret, tenant (`consumers` for personal accounts), refresh token, and the remote path to the database.
- **Self-Hosted SFTP**: Enter the host, port, username, and either password or private key path plus the remote file location (ideal for a TrueNAS or other home server).

Use **Pull Latest** or **Upload Now** for on-demand transfers. When enabled, HustleNest downloads the newest database on startup, uploads every configured interval, and performs a final upload during shutdown. Optional provider packages (google-auth-oauthlib, dropbox, msal, paramiko) are listed in [requirements.txt](requirements.txt).

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
   resources.py           # Resource lookup helpers
   versioning.py          # Centralized application version constant
   data/
      database.py         # SQLite bootstrap and helpers
      order_repository.py # Persistence and reporting queries
      product_repository.py
      settings_repository.py
   models/
      order_models.py     # Dataclasses for orders, items, and app settings
   services/
      order_service.py    # Business logic for invoices and analytics
      cloud_sync_service.py
   ui/
      main_window.py      # Main window with dashboard, orders, reports
      cloud_sync_dialog.py
      product_manager.py
      invoice_manager.py
      cost_component_dialog.py
   viewmodels/
      table_models.py
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
