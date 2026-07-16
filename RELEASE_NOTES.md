# HustleNest v4.0

**Release date:** July 16, 2026

HustleNest v4.0 is the major browser-interface release. The Windows application now starts the production browser workspace and local Python backend together while keeping existing data in the local HustleNest database.

## Highlights

- Complete browser workflows for orders, customers, products, materials, vendors, finance, reports, history, geography, documents, trash, and settings.
- Global search, Quick Add, workflow shortcuts, revision-safe editing, automatic backups, guarded restores, CSV/XLSX import, and optional cloud synchronization.
- Light, Dark, Minty, Solar, Mission Control, and Glass themes with adjustable text sizing and fixed theme backgrounds.
- Browser-editable business identity, logo, owner profile, avatar, and application settings.
- Select the system default browser, a dedicated installed browser, or manual opening at launch.
- Interactive sales map showing every shipped destination together, with market summaries and order navigation.
- Customer lists now include contacts found only in historical orders.

## Fixes

- Fixed material creation failing with `12 values for 13 columns`.
- Fixed the blank Geography screen and restored all-destination map rendering.
- Improved button and text contrast in Mission Control.
- Removed legacy CyberLabLog package naming from HustleNest source and packaging.

## Install or upgrade

1. Download `HustleNestSetup.exe` from this release.
2. Run the installer and follow the prompts.
3. Launch HustleNest from the Start menu or desktop shortcut.

Existing databases and saved preferences remain in `%LOCALAPPDATA%\HustleNest`. Backing up before a major-version upgrade is recommended.

**System requirements:** 64-bit Windows 10 or later, 4 GB RAM minimum, and a modern browser. The installer includes the browser runtime needed by HustleNest.
