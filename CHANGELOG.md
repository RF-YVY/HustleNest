# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
