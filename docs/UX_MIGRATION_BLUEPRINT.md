# HustleNest Workflow and UI Migration Blueprint

## Product direction

HustleNest remains a local-first business application. The existing Python
models, services, SQLite repositories, reporting, backup, and synchronization
features are the system of record. The presentation layer is now a browser UI
connected to a Python HTTP backend bound to the local machine.

The earlier embedded-web-shell proposal was superseded by a standalone local
backend and browser process so users can choose a dedicated work browser. The
desktop UI remains a temporary fallback during parity acceptance. See
[`BROWSER_PARITY_AND_RETIREMENT.md`](BROWSER_PARITY_AND_RETIREMENT.md) for the
completed mapping and retirement gates.

## Information architecture

Replace the nested top-level tab and modal-dialog navigation with a persistent
left navigation rail:

- Home
- Sales
  - Orders
  - Customers
- Inventory
  - Products
  - Materials
  - Vendors
- Finance
  - Expenses
  - Losses
- Insights
  - Reports
  - Map
  - Audit history
- Settings

Documents should be attachments within orders, customers, products, materials,
and vendors. Goals should appear as progress cards on Home with a dedicated
detail view when needed. Charts belong inside Home and Reports rather than in a
separate Graphs destination.

## Global application shell

The shell should provide:

- Persistent left navigation with the active section clearly highlighted.
- A top bar containing global search, sync status, notifications, and user
  actions.
- A primary `Quick add` action for orders, customers, products, materials,
  expenses, and losses.
- Consistent page titles, breadcrumbs, filters, empty states, and loading states.
- One design-token system for color, type, spacing, radius, elevation, and
  semantic statuses.

## Orders vertical slice

Orders are the first migration slice because they connect customers, products,
inventory, pricing, fulfillment, invoices, and reporting.

### Orders workspace

- Searchable and filterable order list on the left or in the primary table.
- Order summary/detail panel that opens without leaving the workspace.
- Status, payment, due date, customer, total, and fulfillment state visible at
  a glance.
- Saved views for open, overdue, unpaid, ready to ship, and completed orders.
- Bulk status and export actions only when records are selected.

### Order composer

Use a focused full-page composer or large side sheet with four sections:

1. Customer
2. Items and pricing
3. Payment and totals
4. Fulfillment

The item editor should support product search, inline quantity and price edits,
clear validation, and an inline `Create product` path. Totals and the primary
Save action remain visible in a sticky footer. Destructive actions do not share
the primary action group.

### Order detail

- Visual status progression from Received through Shipped.
- Customer and fulfillment summary.
- Line items and financial totals.
- Contextual actions such as mark paid, advance status, print invoice, duplicate,
  and cancel.
- Activity history and documents attached to the order rather than hidden in
  separate tools.

## Visual system

- Use a neutral surface palette with one configurable brand accent.
- Present headline metrics as cards with labels, values, trends, and click-through
  actions.
- Use semantic badges for payment, fulfillment, stock, and alert status.
- Prefer 8-pixel spacing increments and a restrained radius/elevation scale.
- Use icons with text for navigation and unfamiliar actions; do not rely on icons
  alone.
- Use skeletons, helpful empty states, confirmation toasts, and inline validation
  instead of repeated modal messages.
- Support light, dark, and system themes from the same token definitions.

## Technical boundaries

Before replacing a screen, expose its operations through presentation-neutral
application services. UI code must not execute SQL directly.

Separate these responsibilities from `order_service.py`:

- PDF and text rendering
- Native file dialogs and paths chosen by the user
- Qt font, page, and document objects

Web-facing bridge methods should accept and return JSON-compatible DTOs rather
than model objects or Qt objects. Each mutation should return the updated record
and a stable error code suitable for inline validation.

## Delivery phases

### Phase 1: Foundation

- Capture the current v3 source in a standalone repository.
- Exclude user databases, backups, credentials, environments, and build output.
- Add repository regression tests, beginning with material creation.
- Record the information architecture and Orders workflow.
- Identify Qt-specific code that must move behind adapters.

### Phase 2: Orders prototype

- Add the web build workspace and shared design tokens.
- Implement the application shell and Orders workspace with fixture data.
- Validate navigation, density, keyboard behavior, and order-entry flow.
- Define the Python-to-web bridge contract.

### Phase 3: Working Orders slice

- Connect the prototype to real order, customer, and product services.
- Add create, update, status, payment, invoice, and validation workflows.
- Run the old and new Orders interfaces side by side during verification.

### Phase 4: Module migration

- Migrate Inventory, Finance, Customers, and Insights in workflow order.
- Move documents and history into their related entity views.
- Retire equivalent Qt Widgets screens only after feature and data parity.

### Phase 5: Packaging decision

- Keep the PySide6 web shell for a local Windows application, or
- expose a FastAPI service when multi-device browser access is required, or
- evaluate a Tauri shell after the Python boundary and packaging strategy are
  stable.

## Acceptance criteria for Phase 1

- The current source can be restored from the standalone repository.
- Databases and backups are not tracked.
- Creating a material is covered by an automated regression test.
- The new navigation and first vertical slice are documented well enough to
  prototype without revisiting the product structure.
