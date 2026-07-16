# Orders presentation bridge contract

This contract defines the boundary between the web Orders workspace and the
existing Python application. Phase 3 implements it as a loopback-only HTTP
service in `hustlenest.web_bridge`; the DTOs remain transport-neutral.

## Phase 3 implemented surface

- `GET /health`
- `GET /api/orders?limit=100`
- `GET /api/orders/{id}`
- `GET /api/orders/metrics`
- `GET /api/customers?query={text}`
- `GET /api/customers/{id}` with follow-up cadence and interaction history
- `POST /api/customers/{id}/interactions` with `values` and `expected_revision`
- `GET /api/products?query={text}`
- `POST /api/products/{id}/photo` with `expected_revision` and a base64-encoded image up to 8 MB
- `GET /api/products/{id}/photo`
- `DELETE /api/products/{id}/photo` with `expected_revision`
- `GET /api/materials?query={text}`
- `GET /api/materials/{id}`
- `POST /api/materials/{id}/adjust` with `values` and `expected_revision`
- `GET /api/vendors?query={text}`
- `GET /api/vendors/{id}`
- `GET /api/finance?limit={count}`
- `GET /api/reports?period={this_month|this_quarter|this_year|last_90_days|all_time}`
- `GET /api/history?query={order}&start_date={date}&end_date={date}&limit={count}`
- `GET /api/geography`
- `GET /api/trash`
- `POST /api/trash/{order|product}/{id}/restore` with `expected_revision`
- `DELETE /api/trash/{order|product}/{id}` with `expected_revision` and explicit confirmation
- `DELETE /api/trash` with the current item count and typed confirmation
- `GET /api/home`
- `GET /api/goals`
- `POST /api/goals` with validated goal `values`
- `PUT /api/goals/{id}` with `values` and `expected_revision`
- `DELETE /api/goals/{id}` with `expected_revision`
- `POST /api/goals/{id}/checkpoints` with `values` and `expected_revision`
- `GET /api/documents`
- `POST /api/documents` with metadata and a base64-encoded file up to 20 MB
- `PUT /api/documents/{id}` with metadata and `expected_revision`
- `DELETE /api/documents/{id}` with `expected_revision` and optional managed-file removal
- `GET /api/documents/{id}/download`
- `GET /api/settings`
- `PUT /api/settings` with `section`, `values`, and `expected_revision`
- `GET /api/backups`
- `PUT /api/backups` with schedule, folder, retention, and `expected_revision`
- `POST /api/backups` with `expected_revision`
- `GET /api/backups/{id}/download`
- `POST /api/backups/{id}/restore` with `expected_revision` and typed confirmation
- `POST /api/quick-add` with `type` and record-specific `values`
- `PUT /api/records/{customer|product|material|vendor|expense|recurring|loss}/{id}` with `values` and `expected_revision`
- `DELETE /api/records/product/{id}` with `expected_revision` to move it to trash
- `GET /api/order-options`
- `POST /api/orders`
- `PUT /api/orders/{id}` with `expected_status`
- `POST /api/orders/{id}/advance` with `expected_status`
- `POST /api/orders/{id}/payment` with current and requested payment status
- `POST /api/orders/{id}/cancel` with `expected_status`
- `GET /api/orders/{id}/invoice` returning the branded PDF invoice or receipt
- `DELETE /api/orders/{id}` with `expected_status` to move it to trash

The Finance payload groups recorded expenses, recurring obligations, and
operational losses. Loss records retain product, material, and order identifiers
so the browser workspace can preserve cross-record navigation.

The Settings payload deliberately excludes payment values, credentials, tokens,
keys, and cloud-sync configuration values. Safe sections can be updated from
the browser with validation and revision conflict protection. Payment methods
expose only labels and configured state; existing destinations can be retained,
replaced, removed, or supplemented without returning their saved values to the
browser. Cloud-sync values remain excluded.

Backups use SQLite's online backup API so committed WAL data is included in a
consistent snapshot. Restore candidates must pass `PRAGMA quick_check`; the
bridge creates a safety snapshot before replacement and returns an explicit
restart requirement. Backup identifiers cover filename, size, and modification
time so stale restore selections are rejected.

The Trash payload combines soft-deleted orders and products with revision tokens.
Restore and permanent-delete actions reject stale items; emptying all trash also
requires both the current item count and the typed phrase `EMPTY TRASH`.
Moving an order to trash deliberately does not alter product inventory, matching
the desktop behavior; cancellation remains the explicit inventory-return action.

Goal payloads expose automatic revenue, profit, order, expense, loss, and CRM
interaction metrics alongside manual progress. Goal and checkpoint mutations
validate date ranges, targets, and alert thresholds, and reject stale revision
tokens before changing the existing goal repositories.

Document uploads are copied into the application’s managed local storage while
metadata remains in the existing documents repository. Links are validated
against orders, CRM customers, products, materials, and vendors. Downloads
require a live saved file; revision checks protect metadata changes, and the
bridge refuses to delete underlying files outside its managed document folder.

Quick Add accepts customers, products, materials, vendors, expenses, recurring
expenses, and losses.
Each type is validated before its existing repository saves the record; duplicate
names or SKUs return stable conflict codes, and invalid fields return field-level
codes. The response identifies the saved record so the browser can refresh and
route directly to its workspace.
Customer, product, material, and vendor summaries include a revision token.
Browser edits preserve fields outside the compact form and reject stale saves
with `record_conflict`, preventing another browser or the desktop app from being
silently overwritten.
Product summaries also include itemized extra unit costs and inventory forecast
signals. Browser product edits validate supported lifecycle statuses and each
nonnegative cost component while preserving the current photo during unrelated
cost or inventory edits.

Product photo uploads accept PNG, JPEG, GIF, and WebP content verified by file
signature rather than filename. Managed images are stored under the local
application media root; replacing or clearing a photo removes the prior managed
file while leaving external desktop-managed source files untouched.
Expense, recurring-expense, and loss revisions cover hidden tags, schedule and
automation fields, recurring/document references,
and linked order, product, or material context so compact edits cannot discard
the bookkeeping relationships behind the visible record. Recurring schedules
require supported frequencies and consistent start, next, and optional end dates.

Status advancement uses the expected current status as a concurrency guard.
If the desktop app or another browser window changed the order first, the
bridge returns `status_conflict` instead of overwriting the newer state.
Payment changes use the same current-value guard. Cancellation restores product
inventory, retains the order as a cancelled record, and removes it from active
metrics. Invoice downloads reuse the desktop invoice renderer and current
invoice, tax, logo, and payment settings.
Order detail responses include the latest audit events. The History payload
supports bounded order-number and date filtering, summarizes affected orders
and net amount changes, and marks whether the related order is still available
for direct browser navigation.
The Geography payload aggregates active addressed orders into parsed city/state
destinations and state totals, includes privacy-safe home-base context, and
returns currently available order summaries for drill-down. It requires no
third-party map tiles or live geocoding.
Create and edit requests return field-level validation codes and update product
inventory using the net quantity change. Customer details entered in the
composer are synchronized with CRM contacts by contact id or normalized name.
Customer search merges formal CRM contacts with distinct customer names stored
on orders. Order-derived entries use a stable presentation key and a null CRM
id until they are synchronized. Customer details include the durable CRM
interaction timeline. Logging an interaction updates last-contacted, preferred
channel, and an optional next follow-up while rejecting stale customer context
and unrelated order links. Material responses include vendor summaries,
stock status, inventory value, and recent transaction activity without exposing
repository models to the browser.
Inventory adjustments accept receiving, consumption, and counted-total actions.
They reject stale revisions and negative resulting stock, then atomically update
the material balance and append an auditable transaction.
Vendor responses summarize purchasing contacts, account preferences, linked
material value, and reorder exposure. Vendor details include presentation-ready
material summaries so the UI can navigate directly into inventory context.

## Rules

- Every method is asynchronous from the frontend's perspective.
- Arguments and return values must be JSON-compatible.
- Dates use `YYYY-MM-DD`; timestamps use ISO 8601 with a timezone.
- Currency values are decimal strings, never binary floating-point values.
- Mutations return the updated record or the saved identity needed for an immediate workspace refresh.
- Expected validation failures return stable field and error codes.
- SQL, Qt widgets, and Python model objects do not cross this boundary.

## Core DTOs

### OrderSummary

- `id`: integer
- `number`: string
- `customer_id`: integer or null
- `customer_name`: string
- `order_date`: date
- `target_completion_date`: date or null
- `status`: string
- `payment_status`: `paid`, `unpaid`, or `partial`
- `total`: decimal string
- `item_count`: integer
- `attention_reasons`: string array

### OrderDetail

Includes every `OrderSummary` field plus:

- `customer`: `CustomerSummary`
- `items`: `OrderLine[]`
- `shipping`: `ShippingDetail`
- `notes`: string
- `tax_rate`: decimal string
- `tax_amount`: decimal string
- `subtotal`: decimal string
- `documents`: `DocumentSummary[]`
- `activity`: `ActivityEntry[]`

### OrderLine

- `id`: integer or null for an unsaved line
- `product_id`: integer or null
- `sku`: string
- `name`: string
- `description`: string
- `quantity`: integer
- `unit_price`: decimal string
- `unit_cost`: decimal string
- `line_total`: decimal string
- `line_profit`: decimal string
- `is_freebie`: boolean

## Queries

- `orders.list(filters)` → `OrderSummary[]`
- `orders.get(order_id)` → `OrderDetail`
- `orders.metrics(filters)` → `OrderMetrics`
- `customers.search(query, limit)` → `CustomerSummary[]`
- `products.search(query, limit)` → `ProductSummary[]`
- `settings.get_order_options()` → statuses, carriers, tax, and numbering options

## Mutations

- `orders.create(draft)` → `OrderDetail`
- `orders.update(order_id, draft)` → `OrderDetail`
- `orders.advance_status(order_id, expected_status)` → `OrderDetail`
- `orders.set_payment(order_id, payment)` → `OrderDetail`
- `orders.cancel(order_id, reason)` → `OrderDetail`
- `orders.duplicate(order_id)` → unsaved `OrderDraft`
- `orders.export_invoice(order_id, destination)` → `ExportResult`

## Error envelope

```json
{
  "ok": false,
  "error": {
    "code": "validation_failed",
    "message": "Review the highlighted fields.",
    "fields": {
      "customer_name": "required"
    }
  }
}
```

Unexpected failures use a general code and are logged in Python without
exposing database paths, credentials, or stack traces to the frontend.
