# HustleNest browser workspace

Phase 3 connects the browser-based Orders workflow to the existing Python
repositories and local SQLite database. The desktop application remains intact.

## Included

- Grouped persistent navigation for Sales, Inventory, Finance, and Insights.
- Orders workspace with summary metrics, filters, search, and list/detail flow.
- Live order selection and guarded status advancement.
- Guarded paid/unpaid changes, inventory-safe cancellation, and branded PDF invoice or receipt downloads.
- Live customer and product selection in the four-step order composer.
- Validated order creation and editing with inventory delta adjustments.
- Tax-aware totals and order-number previews from application settings.
- Connected Customers workspace with contact details, revenue, recent orders, interaction history, and follow-up scheduling.
- Connected Products workspace with stock, itemized unit costing, margin, sales velocity, stockout forecasting, lifecycle status, and order usage.
- Managed local product-photo upload, preview, replacement, and removal with validated image formats and an 8 MB limit.
- Cross-workspace actions that prefill the order composer from a customer or product.
- Reusable navigation and shared presentation DTO definitions for future modules.
- Complete customer coverage merged from CRM contacts and historical orders.
- Connected Materials workspace with replenishment state, vendors, value, activity, and revision-protected stock receiving, consumption, and count corrections.
- Connected Vendors workspace with supplier contacts, purchasing details, and material exposure.
- Connected Finance workspace for expense review, category trends, recurring obligations, and operational losses.
- Connected Reports workspace for period-based revenue, profit, overhead, fulfillment, product, and customer analysis.
- Connected History workspace with order/date/event filtering, financial-impact summaries, CSV export, and per-order activity timelines.
- Offline-friendly Sales Geography workspace with state intensity, home-base context, destination drill-down, and direct order navigation.
- Browser-native Recently Deleted workspace with order/product restoration, guarded permanent deletion, and typed confirmation before emptying trash.
- Connected Home command center for priorities, cash outlook, sales momentum, goals, and cross-workspace shortcuts.
- Browser goal management with automatic or manual metrics, progress checkpoints, thresholds, ownership, revision protection, and deletion.
- Connected Documents library with file-health checks, categories, tags, and linked business-record context.
- Managed local document uploads, validated record links, metadata editing, downloads, and safe record/file removal choices.
- Privacy-safe editable Settings for business, order, invoice, tax, inventory, payment methods, and browser-launch preferences, with masked payment destinations and protected sync summaries.
- Saved browser light/dark appearance, managed business-logo upload, sidebar branding, and browser editing for the desktop fallback dashboard layout.
- Masked browser configuration for local-folder, Google Drive, Dropbox, OneDrive, and SFTP sync, plus snapshot-safe upload and confirmed, backed-up, integrity-checked cloud pulls.
- Browser backup and recovery management with automatic schedules, online SQLite snapshots, retention limits, downloads, health validation, safety copies, and typed restore confirmation.
- Browser CSV/XLSX import for products, orders, and customers with file preview, automatic or manual column mapping, required-field checks, duplicate handling, and row-level results.
- Global Quick Add forms for customers, products, materials, vendors, expenses, recurring expenses, and losses, with validated local persistence and automatic workspace refresh.
- Global search across orders, customers, products, materials, vendors, finance records, and documents, with keyboard navigation and direct record opening.
- In-place editing for customers, products, materials, and vendors with validation, stale-change protection, and automatic workspace refresh.
- Finance detail editing for expenses, recurring schedules, and losses, preserving hidden bookkeeping context while preventing stale overwrites.
- Clear connected, empty-database, and offline/demo states.
- Four-section order composer for customer, items, payment, and fulfillment.
- Light and dark visual systems with responsive desktop and mobile layouts.
- Rendered-output tests that verify product metadata and the key Orders surface.

## Run locally

For normal source use, build once and then start the browser server and backend
together from the repository root:

```powershell
cd web
npm install
npm run build
cd ..
python -m hustlenest.browser_app
```

The unified launcher honors the automatic browser preference saved in Settings,
including the manual-open option. For frontend development, start only the data
bridge in one terminal:

```powershell
python -m hustlenest.web_bridge
```

Then start the development server from this `web` directory:

```powershell
npm run dev
```

Open `http://localhost:3000/`.

The bridge listens only on `127.0.0.1:8765`. Override its frontend URL with
`NEXT_PUBLIC_HUSTLENEST_API_URL` when needed.

Creating or editing an order updates the same SQLite database used by the
desktop application. Order edits preserve inventory by applying only the
difference between the previous and new product quantities.

## Validate

```powershell
npm test
```

The web test command creates the production build and verifies the
server-rendered Orders workspace. From the repository root, run
`python -m unittest discover -s tests -v` to verify the bridge and repository
regressions against isolated temporary databases.
