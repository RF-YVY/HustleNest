# Changelog

All notable changes to this project will be documented in this file.

## [4.0] - 2026-07-16

### Added
- Complete browser workspaces for orders, customers, products, materials, vendors, finance, reports, history, geography, documents, trash, and settings.
- Persistent Light, Dark, Minty, Solar, Mission Control, and Glass themes with adjustable application text sizing.
- Browser-editable business identity, logo, owner profile, avatar, launch-browser preference, backup, import, and cloud-sync settings.
- Interactive multi-destination OpenStreetMap sales view with an offline state-grid alternative.
- Global search, Quick Add, revision-safe editing, guarded database restore, and expanded browser report exports.

### Changed
- The packaged Windows application now launches the browser UI and local Python backend as one application.
- Customer lists merge CRM contacts with names found only in historical orders.
- Navigation and record workflows were regrouped around sales, business operations, and analysis.

### Fixed
- Corrected material insertion so all 13 database columns receive matching values.
- Restored Geography rendering and display of all shipped destinations.
- Improved Mission Control contrast and replaced the Terminal theme with a fixed-background Glass theme.

## [3.0] - 2026-02-04

### Added
- **Dark Mode**: New appearance settings with full dark/light theme toggle that persists across sessions.
- **Dashboard Customization**: Collapsible/hideable dashboard sections with click-to-toggle headers. Configure visibility and default state in Advanced Settings → Dashboard.
- **Soft Delete & Trash**: Deleted orders and products are now moved to a "Recently Deleted" area instead of being permanently removed. Restore or permanently delete items from Settings → Recently Deleted.
- **Multiple Chart Types**: Enhanced Graphs tab with chart type selector (Bar, Line, Pie, Customer Breakdown).
- **Advanced Settings Dialog**: Centralized access to Theme, Dashboard, Backup, Import, and Export features.
- **Database Backup Scheduler**: Automatic daily/weekly backups with configurable retention, backup folder selection, and one-click restore.
- **Data Import Wizard**: Import products from CSV or Excel files with intelligent column auto-mapping.
- **PDF Report Export**: Generate professional PDF reports including:
  - Sales Report with order details
  - Inventory Report with stock levels and values
  - Profit & Loss Statement
  - Customer Report with rankings
  - Period Comparison (month vs month, quarter vs quarter, year vs year)
- **Skip Version Updates**: Update notifications now include "Skip This Version" and "Download" buttons.

### Changed
- Added `openpyxl` to requirements for Excel file import support.

## [2.2.1] - 2026-02-02

### Fixed
- Included cloud sync dependencies in the Windows installer build so `requests` is bundled.

## [2.2.0] - 2026-01-10

### Added
- Sales tax summaries can export quarterly and year-end reports to CSV or PDF.
- CRM tab can import contacts sourced from historical orders to seed outreach campaigns.

### Changed
- Losses and expenses entries now share the materials category dropdown for consistent tagging across business tools.

## [2.1.1] - 2026-01-09

### Changed
- Saving an existing order now clears the selection and resets the editor for the next entry.
- Orders tab inputs include inline labels and tooltips around product, quantity, and pricing fields for faster onboarding.

### Fixed
- Removed the placeholder "get started" message from exported invoice comments so PDFs only include saved content.

## [2.1] - 2026-01-08

### Added
- Recent Orders panel now surfaces a concise product summary per order and receives additional layout space for faster scanning.
- Selecting an existing order automatically repopulates the Order Items grid, making it easy to confirm line details before editing.

### Fixed
- Corrected the SQL parameter count when creating orders so new records persist without binding errors.
- Hardened product updates to tolerate empty optional fields, preventing crashes when descriptions or photos are missing.

### Documentation
- Updated the in-app About page to reflect the latest workflow improvements.
