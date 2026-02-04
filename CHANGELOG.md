# Changelog

All notable changes to this project will be documented in this file.

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
