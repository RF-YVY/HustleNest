# Browser parity and desktop retirement

## Status

The local Python backend and browser UI now cover the business workflows that
previously required the PySide6 desktop interface. SQLite remains the system of
record. The desktop UI is intentionally retained as a fallback until packaged
browser startup and real-data acceptance checks are complete.

## Workflow parity

| Desktop area | Browser destination | Status |
| --- | --- | --- |
| Dashboard and notifications | Home priorities, goals, cash outlook, recent orders | Complete |
| Orders and invoice manager | Orders composer/detail, lifecycle, payment, PDF invoice/receipt | Complete |
| Customers and CRM | Customers, contact promotion from historical orders, interactions and follow-ups | Complete |
| Products and product manager | Products, costing, forecasts, photos, recoverable trash | Complete |
| Materials and transactions | Materials, receive/consume/count adjustments and history | Complete |
| Vendors | Vendors with linked materials and inventory exposure | Complete |
| Expenses, recurring expenses, and losses | Finance | Complete |
| Documents | Documents with managed uploads, links, tags, download, and guarded removal | Complete |
| Goals | Home goal editor and checkpoints | Complete |
| Reports, graphs, and tax exports | Reports with period analytics, CSV and PDF downloads | Complete |
| Map | Sales Geography | Complete |
| Order history | Activity History and order-local timelines | Complete |
| Backup and restore | Settings | Complete |
| CSV/XLSX import | Settings | Complete |
| Business, invoice, tax, payment, appearance, and browser preferences | Settings | Complete |
| Cloud sync providers and manual transfer | Settings | Complete |
| About and update links | Settings / About HustleNest | Complete |

Record deletion uses revision guards. Orders and products use recoverable
trash; operational records use confirmed deletion, matching the legacy desktop
behavior. Cloud credentials, payment destinations, and other saved secrets are
never returned to the browser.

## Acceptance checklist before making desktop fallback-only

1. Make a verified local database backup.
2. Run the backend and browser UI against a copy of the production database.
3. Confirm record counts for orders, customers, products, materials, vendors,
   expenses, recurring expenses, losses, documents, and goals.
4. Complete one create/edit/delete or trash/restore cycle for every record type.
5. Generate an invoice, order CSV, sales report PDF, and tax export.
6. Preview a representative import without executing it, then test an import on
   the copied database.
7. Test backup creation and restore on the copied database.
8. If cloud sync is used, test upload and pull with a disposable remote copy.
9. Verify the configured automatic-browser choice for each Windows user profile.
10. Keep the desktop executable available for at least one release cycle while
    users report any missing edge cases.

## Retirement sequence

After the checklist passes, change the normal launcher to start the Python
backend and browser UI. Keep the desktop launcher as an explicitly labeled
fallback. Do not remove PySide6 screens or their service integrations until one
release cycle completes without a blocking parity issue. After that period,
the Qt presentation layer can be removed in a separate cleanup release; the
repositories, services, SQLite schema, PDF rendering, backup, import, and sync
implementations remain in use by the backend.

The backend binds to `127.0.0.1` by default. Do not expose it to a LAN or the
internet without adding authentication, TLS, and a deployment-specific threat
review.
