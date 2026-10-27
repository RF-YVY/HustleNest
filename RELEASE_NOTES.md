# HustleNest v4.3.0

**Release date:** October 27, 2026

## Bookkeeping and CPA handoff

- New Books & banking workspace: Accounts → Record money → Match statements → Review costs → Close & export.
- Balanced journal entries use integer cents. Record dated receipts, refunds, fees, inventory purchases/usage/write-offs, equipment, owner contributions/draws, loan principal, tax remittances, and transfers.
- Customer payments can split sales tax and withheld processing fees and optionally update a linked order's paid balance. Reversals retain original records and correct synchronized order balances.
- Real money remains in Books when an order is cancelled or trashed. Operational reports continue excluding those orders.
- Import statement CSVs, detect duplicate bank references, match exact account/amount entries, correct imports with retained history, and reconcile to statement ending balances.
- Reconciled accounts and closed book periods reject backdated changes. Journal entries cannot be edited or deleted; use dated reversals or CPA adjustments.
- Classify expenses and write-offs already included in order costs to prevent a second operational deduction.
- CPA ZIP selection includes book financial summary, journal with source snapshots, account balances, statement matches, reconciliations, classifications, and import corrections.

## Clearer everyday flow

- Renamed $0 replacement disclosure to replacement costs. Free items reduce profit through their actual cost, not through a reduction of sales revenue.
- Corrected legacy Net Revenue / margin calculations and partial-payment cash outlook logic.
- Added an order Payment / refund shortcut, contextual explanations, CSV template, empty-state guidance and responsive bookkeeping layout.
- Removed nonfunctional three-dot controls. Owner identity is a static display; Settings remains the single settings destination.
- Grouped spending records as Expenses & costs and actual financial records as Books & banking.

- Added a visible experimental-software reminder in Settings and a full disclaimer in About: use at your own risk, no warranties to the extent permitted by law, independent records, regular off-device/separate-location backups and restore checks.

## Upgrade and first use

Download and run HustleNestSetup.exe. Existing orders and spending records remain intact. Historical paid flags have no reliable receipt dates and are not automatically posted to the new books. Set up verified opening balances or backfill actual transactions with your CPA; do not add operational report totals to book totals.

This release provides manual statement import and reconciliation, not live bank feeds, payroll, automatic depreciation, tax filing, or certified tax returns. See docs/BOOKKEEPING_GUIDE.md for the setup and reporting basis.
