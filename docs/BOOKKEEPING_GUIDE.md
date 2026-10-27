# Books & banking: owner and CPA guide

## Two reports with different purposes

**Reports / order performance** uses order dates and saved order-item costs. It answers production and profitability questions. Quotes, drafts, cancelled and trashed orders contribute no money to those totals. A $0 item contributes no revenue; its cost reduces profit once. Replacement costs are a disclosure, not an extra deduction.

**Books & banking** uses explicitly dated financial postings. It answers what was received, paid, owed, invested or withdrawn. Cancelling or trashing an operational order does not erase real receipts, refunds, purchases or supporting snapshots. Never add order-performance totals to book totals.

The book income/expense summary covers the selected dates. Account balances and the balance sheet are cumulative through the selected end date. Equity includes accumulated earnings. The balance check should be $0.00. These are records entered by the user, not an automatic tax return or a certification of completeness.

## 1. Set up accounts

Create each business checking, savings, cash and credit-card account. Enter a verified opening date and balance immediately before the transactions you will record. For a card, a positive opening balance means money owed. Bank openings offset opening equity. Use CPA-reviewed journal adjustments for other opening inventory, equipment, debt and equity balances.

No historical payment dates are guessed. Old paid flags and accumulated amounts remain operational data. Either backfill actual bank/receipt transactions or start at a CPA-approved opening date; do not backfill transactions that are already included in the opening balance.

## 2. Record actual money

Choose what happened, its actual date, account, amount, description and bank/receipt reference. Amounts allow two decimal places and are stored in integer cents.

- **Customer payment:** gross amount received. Separate collected sales tax from sales income and optionally split withheld processing fees. Example: $110 gross, $10 tax and $3 fee posts $107 to the bank, $100 sales, $10 tax payable and $3 fee expense.
- **Customer refund:** reduces sales and, if applicable, sales tax payable. Link the original order even if it is cancelled or trashed.
- **Operating expense / fee:** costs not already accounted for as inventory or an asset. Do not enter a fee twice when it was split from a receipt.
- **Buy hats / materials:** moves purchase cost into inventory. **Use inventory / product cost** subsequently recognizes inventory actually consumed as cost of goods sold. **Inventory damaged / wasted** recognizes inventory written off at actual cost, never retail selling price. The book inventory amount is separate from the operational physical stock count.
- **Buy equipment:** records an asset. Your CPA determines depreciation, capitalization and tax treatment.
- **Transfer / pay credit card:** moves value between accounts, not income or another expense.
- **Owner contribution / withdrawal:** changes equity, not ordinary sales or expenses.
- **Loan received / principal repaid:** changes liabilities. Record interest separately as an expense.
- **Pay collected sales tax:** reduces the liability, not another expense.

Link existing spending records and documents where available. A spending record must match the amount and can have only one active linked posting. A reviewed inventory/order cost cannot be posted again as overhead.

The order Payment / refund shortcut opens this form with the order selected. For a genuinely new payment/refund, choose **Update linked order amount paid**. Historical payments already reflected in an order must leave that option unchecked. No money is transferred by these forms; they record what already happened.

Journal entries are immutable. Use **Correct with reversal** and an open correction date to retain the original record. A reversal also corrects an order balance that was synchronized by the original posting. Follow it with the correct posting if appropriate.

Estimated owner time may be useful for pricing but is not a wage deduction paid to yourself as a sole proprietor. Enter actual accountant-approved costs in the books.

## 3. Match bank/card statements

Download the CSV template. The required columns are `date,description,amount,reference`. Use YYYY-MM-DD dates, signed amounts and a unique bank reference for every row. Deposits are positive, spending negative; credit-card purchases negative, repayments positive.

Importing statement rows does not create income or expenses. Match each row to an existing posting with the exact account and amount. A receipt with withheld fees matches the net bank deposit. Record the receipt/fee split before matching.

Re-importing an identical bank reference skips it; changed amounts or dates for the same reference are rejected. **Correct imported row** can amend an unmatched, unreconciled import with a required reason. Its original values and reason remain in the CPA correction export. Undo an incorrect match before correcting or rematching.

After all imported rows through the statement end date are matched, enter the ending balance and reconcile. The cleared balance includes opening entries and matched entries through that date. It must equal the statement. Outstanding book entries may remain unmatched. For credit cards enter the amount owed as positive. Future statement dates are rejected.

Reconciliation protects the account against backdated postings, match removal and import corrections through its end date. Later corrections use an open date. Verify that the complete statement was imported before accepting reconciliation; the app cannot detect rows omitted from the file supplied to it.

## 4. Review costs and write-offs

Old records begin as **Needs review** and remain included in operational overhead/write-offs until deliberately classified. Add an explanation of each classification for your CPA.

A purchase already included in order costs should not also reduce operational profit as overhead. Inventory purchases, equipment, transfers, loan principal and owner withdrawals have their own treatment. Separately recorded write-offs can be classified as already included in order costs or another inventory adjustment. Review these against receipts and the actual order/inventory records.

Classification affects operational report deductions. It does not create or alter bank postings. Books have their own postings, and bank imports are matches rather than additional deductions. Avoid manually posting the same purchase more than once.

## 5. Close and export

Reconcile all business accounts through the proposed close date, review classifications, then close the bookkeeping period. Closing locks dated book entries and classifications through that date. It does not freeze the independent order-management screens. Use later corrections rather than rewriting closed financial history.

CPA journal adjustments are available for opening inventory, depreciation, and other balanced accountant-reviewed entries. Choose the debit and credit accounts deliberately.

In Reports, apply the desired dates, choose **CPA package (ZIP)**, and click Download. Select the book summary, journal, account balances, bank matches, reconciliations, import correction history, expense/write-off classifications, and any operational CSVs/PDFs your CPA requests. The journal includes source snapshots and record IDs; originals should also be retained in Documents and your receipts archive. Current inventory PDF exports are operational snapshots, not historical inventory valuations.

## Current limits

- Manual bank/card statement import; no bank-feed connection or movement of funds.
- One bank row matches one bank-side journal entry. Complex combined deposits need an appropriate aggregated posting or CPA adjustment; automatic many-to-many matching is not provided.
- User-entered inventory consumption and accountant adjustments; no automatic historical tax-inventory valuation, depreciation, payroll or tax-return filing.
- Dated postings and classifications do not by themselves establish a tax accounting method. Have your CPA confirm the method, opening balances, inventory treatment and deductions.
- Monthly statement completeness, source-document retention and duplicate review remain necessary. The app cannot infer missing transactions from order flags.

## Interface changes

Navigation separates **Expenses & costs** (source spending/obligation records) from **Books & banking** (dated financial postings). Numbered task tabs follow the monthly workflow. Transaction choices include plain-language explanations, with extra links and accountant controls in disclosures. Success/error messages explain the next step. The order's inactive ellipsis has been replaced with Payment / refund, and owner identity is a static display; Settings is the single settings destination.
