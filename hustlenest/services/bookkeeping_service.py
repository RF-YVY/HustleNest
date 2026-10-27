"""Append-only, cent-based bookkeeping and bank statement reconciliation.

Independent of operational orders: cancelling an order never erases real cash.
Historical cumulative payment flags are not silently converted to dated receipts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..data.database import create_connection

NOMINAL = [
    ('sales', 'Sales income', 'income'), ('refunds', 'Customer refunds', 'income'),
    ('overhead', 'Operating expenses', 'expense'), ('fees', 'Payment processing fees', 'expense'),
    ('cogs', 'Cost of goods sold', 'expense'), ('writeoffs', 'Inventory write-offs at cost', 'expense'), ('inventory', 'Inventory at cost', 'asset'),
    ('equipment', 'Equipment at cost', 'asset'), ('depreciation', 'Depreciation expense', 'expense'),
    ('accumulated_depreciation', 'Accumulated depreciation', 'asset'), ('tax', 'Sales tax payable', 'liability'),
    ('loan', 'Loan principal payable', 'liability'), ('capital', 'Owner contributions / opening equity', 'equity'),
    ('draw', 'Owner withdrawals', 'equity'),
]


def initialize_schema(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS book_accounts (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL, is_bank INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS book_transactions (
            id INTEGER PRIMARY KEY, transaction_date TEXT NOT NULL, kind TEXT NOT NULL,
            description TEXT NOT NULL, reference TEXT NOT NULL DEFAULT '',
            order_id INTEGER, expense_id INTEGER, document_id INTEGER,
            reversed_id INTEGER UNIQUE, request_id TEXT UNIQUE, source_snapshot TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS book_entries (
            id INTEGER PRIMARY KEY, transaction_id INTEGER NOT NULL REFERENCES book_transactions(id),
            account_id INTEGER NOT NULL REFERENCES book_accounts(id), cents INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_book_entries_account ON book_entries(account_id);
        CREATE TABLE IF NOT EXISTS book_bank_rows (
            id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES book_accounts(id),
            transaction_date TEXT NOT NULL, description TEXT NOT NULL, cents INTEGER NOT NULL,
            reference TEXT NOT NULL DEFAULT '', fingerprint TEXT UNIQUE NOT NULL,
            matched_entry_id INTEGER UNIQUE REFERENCES book_entries(id));
        CREATE TABLE IF NOT EXISTS book_bank_row_history (
            id INTEGER PRIMARY KEY, bank_row_id INTEGER NOT NULL, original_json TEXT NOT NULL,
            reason TEXT NOT NULL, changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS book_reconciliations (
            id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES book_accounts(id),
            end_date TEXT NOT NULL, ending_cents INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(account_id, end_date));
        CREATE TABLE IF NOT EXISTS book_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS book_entries_no_update BEFORE UPDATE ON book_entries BEGIN SELECT RAISE(ABORT,'Book entries are immutable. Post a reversal.'); END;
        CREATE TRIGGER IF NOT EXISTS book_entries_no_delete BEFORE DELETE ON book_entries BEGIN SELECT RAISE(ABORT,'Book entries are immutable. Post a reversal.'); END;
        CREATE TRIGGER IF NOT EXISTS book_transactions_no_update BEFORE UPDATE ON book_transactions BEGIN SELECT RAISE(ABORT,'Book transactions are immutable. Post a reversal.'); END;
        CREATE TRIGGER IF NOT EXISTS book_transactions_no_delete BEFORE DELETE ON book_transactions BEGIN SELECT RAISE(ABORT,'Book transactions are immutable. Post a reversal.'); END;
        CREATE TABLE IF NOT EXISTS loss_treatments (
            loss_id INTEGER PRIMARY KEY, treatment TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS expense_treatments (
            expense_id INTEGER PRIMARY KEY, treatment TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    if not any(row[1] == 'source_snapshot' for row in connection.execute('PRAGMA table_info(book_transactions)')):
        connection.execute("ALTER TABLE book_transactions ADD COLUMN source_snapshot TEXT NOT NULL DEFAULT '{}'")
    for code, name, kind in NOMINAL:
        connection.execute('INSERT OR IGNORE INTO book_accounts(code,name,kind) VALUES (?,?,?)', (code, name, kind))


def cents(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.quantize(Decimal('.01')) or abs(number) > Decimal('9999999999'):
            raise ValueError('Use a finite amount with no more than two decimal places.')
        return int(number * 100)
    except (InvalidOperation, TypeError):
        raise ValueError('Enter a valid amount.') from None


def money(value):
    return f'{Decimal(value) / 100:.2f}'


def day(value):
    try:
        parsed = date.fromisoformat(str(value))
        return parsed.isoformat()
    except (TypeError, ValueError):
        raise ValueError('Enter a valid date (YYYY-MM-DD).') from None


def _account(connection, account_id):
    row = connection.execute('SELECT * FROM book_accounts WHERE id=?', (int(account_id),)).fetchone()
    if not row:
        raise ValueError('Choose an existing account.')
    return row


def _open_date(connection, transaction_date, account_ids=()):
    closed = connection.execute("SELECT value FROM book_settings WHERE key='closed_through'").fetchone()
    if closed and transaction_date <= closed['value']:
        raise ValueError('This accounting period is closed. Use a current-date correction.')
    for account_id in account_ids:
        last = connection.execute('SELECT MAX(end_date) AS end_date FROM book_reconciliations WHERE account_id=?', (account_id,)).fetchone()
        if last['end_date'] and transaction_date <= last['end_date']:
            raise ValueError('This account is already reconciled through that date. Use a later correction date.')


def _insert(connection, transaction_date, kind, description, entries, payload=None):
    payload = payload or {}
    if not description.strip() or len(description) > 1000:
        raise ValueError('Add a description of up to 1,000 characters.')
    if not entries or sum(amount for _, amount in entries) != 0:
        raise ValueError('Journal entries must balance.')
    _open_date(connection, transaction_date, [account for account, _ in entries])
    snapshot = {}
    for field, table in [('order_id','orders'),('expense_id','expenses'),('document_id','documents')]:
        if payload.get(field):
            source = connection.execute(f'SELECT * FROM {table} WHERE id=?', (payload[field],)).fetchone()
            if source:
                snapshot[field] = dict(source)
    if payload.get('update_order_payment') in {True, 'on', 'true'} and kind in {'receipt','refund'}:
        snapshot['order_payment_delta_cents'] = cents(payload.get('amount')) * (1 if kind == 'receipt' else -1)
    cursor = connection.execute('''INSERT INTO book_transactions(transaction_date,kind,description,reference,order_id,expense_id,document_id,reversed_id,request_id,source_snapshot)
        VALUES (?,?,?,?,?,?,?,?,?,?)''', (transaction_date, kind, description.strip(), str(payload.get('reference', ''))[:500],
        payload.get('order_id') or None, payload.get('expense_id') or None, payload.get('document_id') or None,
        payload.get('reversed_id'), payload.get('request_id') or None, json.dumps(snapshot)))
    transaction_id = cursor.lastrowid
    for account, amount in entries:
        _account(connection, account)
        if amount:
            connection.execute('INSERT INTO book_entries(transaction_id,account_id,cents) VALUES (?,?,?)', (transaction_id, account, amount))
    return transaction_id


def create_account(payload):
    name = str(payload.get('name', '')).strip()
    kind = payload.get('kind', 'asset')
    if not name or len(name) > 100 or kind not in {'asset', 'liability'}:
        raise ValueError('Enter an account name and choose bank/cash or credit card.')
    opening = cents(payload.get('opening_balance', 0))
    # Positive credit-card balance means an amount owed.
    signed_opening = -opening if kind == 'liability' else opening
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        cursor = connection.execute('INSERT INTO book_accounts(name,kind,is_bank) VALUES (?,?,1)', (name, kind))
        if opening:
            equity = connection.execute("SELECT id FROM book_accounts WHERE code='capital'").fetchone()['id']
            _insert(connection, day(payload.get('opening_date')), 'opening', f'Opening balance: {name}', [(cursor.lastrowid, signed_opening), (equity, -signed_opening)])
        return cursor.lastrowid


def post_transaction(payload):
    transaction_date = day(payload.get('date'))
    amount = cents(payload.get('amount'))
    tax = cents(payload.get('sales_tax', 0))
    fee = cents(payload.get('processing_fee', 0))
    if fee < 0 or fee >= amount:
        raise ValueError("Processing fee must be nonnegative and less than the total.")
    if amount <= 0 or tax < 0 or tax > amount:
        raise ValueError('Amount must be positive; sales tax must be between zero and the total amount.')
    kind = payload.get('kind')
    rules = {
        'receipt': ('sales', 1), 'refund': ('refunds', -1), 'expense': ('overhead', -1),
        'fee': ('fees', -1), 'inventory_purchase': ('inventory', -1), 'equipment_purchase': ('equipment', -1),
        'owner_contribution': ('capital', 1), 'owner_draw': ('draw', -1),
        'loan_received': ('loan', 1), 'loan_principal_payment': ('loan', -1), 'sales_tax_payment': ('tax', -1),
    }
    if kind not in set(rules) | {'transfer', 'inventory_used', 'inventory_writeoff'}:
        raise ValueError('Choose a valid transaction type.')
    if fee and kind != "receipt":
        raise ValueError("Processing fees can be split from customer receipts only.")
    if tax and kind not in {'receipt', 'refund'}:
        raise ValueError('Only receipts and refunds can include collected sales tax.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        request_id = str(payload.get('request_id', ''))
        if request_id:
            prior = connection.execute('SELECT id FROM book_transactions WHERE request_id=?', (request_id,)).fetchone()
            if prior:
                return prior['id']
        ids = {row['code']: row['id'] for row in connection.execute('SELECT id,code FROM book_accounts WHERE code IS NOT NULL')}
        if kind in {'inventory_used', 'inventory_writeoff'}:
            entries = [(ids['cogs' if kind == 'inventory_used' else 'writeoffs'], amount), (ids['inventory'], -amount)]
        else:
            account = _account(connection, payload.get('account_id', 0))
            if not account['is_bank']:
                raise ValueError('Choose a bank, cash, or credit-card account.')
            if kind == 'transfer':
                target = _account(connection, payload.get('target_account_id', 0))
                if not target['is_bank'] or target['id'] == account['id']:
                    raise ValueError('Choose a different bank, cash, or credit-card destination.')
                entries = [(account['id'], -amount), (target['id'], amount)]
            else:
                code, sign = rules[kind]
                entries = [(account['id'], sign * amount - fee), (ids[code], -sign * (amount - tax))]
                if fee:
                    entries.append((ids['fees'], fee))
                if tax:
                    entries.append((ids['tax'], -sign * tax))
        if payload.get('order_id'):
            order = connection.execute('SELECT * FROM orders WHERE id=?', (int(payload['order_id']),)).fetchone()
            if not order:
                raise ValueError('The linked order does not exist.')
            if order['status'].strip().casefold() in {'quote', 'draft'}:
                raise ValueError('Convert a quote or draft before recording actual customer money.')
        for field, table in [('expense_id', 'expenses'), ('document_id', 'documents')]:
            if payload.get(field) and not connection.execute(f'SELECT id FROM {table} WHERE id=?', (int(payload[field]),)).fetchone():
                raise ValueError(f'The linked {field.replace("_id", "")} does not exist.')
        if payload.get('expense_id'):
            expense = connection.execute('SELECT amount FROM expenses WHERE id=?', (int(payload['expense_id']),)).fetchone()
            if kind not in {'expense','fee','inventory_purchase','equipment_purchase','owner_draw','loan_principal_payment','transfer'} or cents(expense['amount']) != amount:
                raise ValueError('An expense link must match the spending amount and a spending transaction type.')
            treatment = connection.execute('SELECT treatment FROM expense_treatments WHERE expense_id=?', (int(payload['expense_id']),)).fetchone()
            if treatment and treatment['treatment'] in {'inventory_purchase','already_in_order_cost'} and kind in {'expense','fee'}:
                raise ValueError('This purchase was classified as inventory / already in order costs. Post it to Inventory instead of deducting it as overhead again.')
            prior = connection.execute('SELECT t.id FROM book_transactions t WHERE expense_id=? AND NOT EXISTS (SELECT 1 FROM book_transactions r WHERE r.reversed_id=t.id)', (int(payload['expense_id']),)).fetchone()
            if prior:
                raise ValueError('This expense already has a bookkeeping transaction. Review or reverse it instead of posting twice.')
        updated_paid = None
        if payload.get('update_order_payment') in {True, 'on', 'true'}:
            if not payload.get('order_id') or kind not in {'receipt', 'refund'}:
                raise ValueError('Updating an order balance requires a linked customer payment or refund.')
            total = Decimal(str(order['total_amount'])) + (Decimal(str(order['tax_amount'])) if order['tax_included_in_total'] else 0)
            total_cents = int(total.quantize(Decimal('.01')) * 100)
            prior = connection.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?', (order['id'],)).fetchone()
            paid = total_cents if order['is_paid'] else int(Decimal(str(prior['amount_paid'] if prior else 0)).quantize(Decimal('.01')) * 100)
            updated_paid = paid + (amount if kind == 'receipt' else -amount)
            if updated_paid < 0 or updated_paid > total_cents:
                raise ValueError('This would make the order paid amount negative or exceed its total. For historical payments already reflected in the order, leave Update order amount paid unchecked.')
        transaction_id = _insert(connection, transaction_date, kind, str(payload.get('description', '')), entries, payload)
        if updated_paid is not None:
            connection.execute('''INSERT INTO order_workflow(order_id,amount_paid) VALUES (?,?)
                ON CONFLICT(order_id) DO UPDATE SET amount_paid=excluded.amount_paid,updated_at=CURRENT_TIMESTAMP''', (order['id'],float(money(updated_paid))))
            connection.execute('UPDATE orders SET is_paid=? WHERE id=?', (int(total_cents > 0 and updated_paid == total_cents),order['id']))
            connection.execute('INSERT INTO order_history(order_id,order_number,event_type,description,amount_delta) VALUES (?,?,?,?,?)',
                (order['id'],order['order_number'],'Payment recorded',f'Book transaction #{transaction_id}: {kind}; amount paid updated.',0.0))
        return transaction_id


def post_adjustment(payload):
    amount = cents(payload.get('amount'))
    debit = int(payload.get('debit_account_id', 0))
    credit = int(payload.get('credit_account_id', 0))
    if amount <= 0 or debit == credit:
        raise ValueError('Use a positive amount and two different accounts.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        _account(connection, debit)
        _account(connection, credit)
        return _insert(connection, day(payload.get('date')), 'adjustment', str(payload.get('description', '')), [(debit, amount), (credit, -amount)], payload)


def reverse_transaction(payload):
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        original = connection.execute('SELECT * FROM book_transactions WHERE id=?', (int(payload.get('transaction_id', 0)),)).fetchone()
        if not original or original['reversed_id']:
            raise ValueError('Choose an original transaction to reverse.')
        if connection.execute('SELECT id FROM book_transactions WHERE reversed_id=?', (original['id'],)).fetchone():
            raise ValueError('This transaction has already been reversed.')
        entries = [(row['account_id'], -row['cents']) for row in connection.execute('SELECT account_id,cents FROM book_entries WHERE transaction_id=?', (original['id'],))]
        data = dict(order_id=original['order_id'], document_id=original['document_id'], reversed_id=original['id'], reference=payload.get('reference', ''))
        snapshot = json.loads(original['source_snapshot'])
        delta = snapshot.get('order_payment_delta_cents',0)
        order = connection.execute('SELECT * FROM orders WHERE id=?',(original['order_id'],)).fetchone() if original['order_id'] else None
        corrected_paid = None
        if delta and order:
            workflow = connection.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?',(order['id'],)).fetchone()
            paid = int(Decimal(str(workflow['amount_paid'] if workflow else 0)).quantize(Decimal('.01'))*100)
            corrected_paid = paid - delta
            total = Decimal(str(order['total_amount'])) + (Decimal(str(order['tax_amount'])) if order['tax_included_in_total'] else 0)
            total_cents = int(total.quantize(Decimal('.01'))*100)
            if not 0 <= corrected_paid <= total_cents:
                raise ValueError('The order amount changed after this payment. Review its paid balance before reversing.')
        transaction_id = _insert(connection, day(payload.get('date')), 'reversal', str(payload.get('description', '')), entries, data)
        if corrected_paid is not None:
            connection.execute('UPDATE order_workflow SET amount_paid=?,updated_at=CURRENT_TIMESTAMP WHERE order_id=?',(float(money(corrected_paid)),order['id']))
            connection.execute('UPDATE orders SET is_paid=? WHERE id=?',(int(total_cents > 0 and corrected_paid==total_cents),order['id']))
            connection.execute('INSERT INTO order_history(order_id,order_number,event_type,description,amount_delta) VALUES (?,?,?,?,?)',
                (order['id'],order['order_number'],'Payment reversed',f'Book transaction #{transaction_id} reverses #{original["id"]}; order paid balance corrected.',0.0))
        return transaction_id


def import_bank_rows(payload):
    rows = payload.get('rows', [])
    if payload.get('csv_text'):
        import csv
        import io
        text = str(payload['csv_text'])
        if len(text) > 2_000_000:
            raise ValueError('Statement CSV must be under 2 MB.')
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        required = {'date', 'description', 'amount', 'reference'}
        if not reader.fieldnames or not required.issubset({name.strip().lower() for name in reader.fieldnames}):
            raise ValueError('CSV needs date, description, amount, and reference columns.')
        rows = [{str(key).strip().lower(): value for key, value in row.items() if key} for row in reader]

    if not isinstance(rows, list) or not 0 < len(rows) <= 5000:
        raise ValueError('Import between 1 and 5,000 statement rows.')
    added = 0
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        account = _account(connection, payload.get('account_id', 0))
        if not account['is_bank']:
            raise ValueError('Choose a bank or card account.')
        for row in rows:
            transaction_date = day(row.get('date'))
            amount = cents(row.get('amount'))
            if not amount:
                raise ValueError('Statement amounts must be non-zero.')
            description = str(row.get('description') or '').strip()[:1000]
            reference = str(row.get('reference') or '').strip()[:500]
            if not description or not reference:
                raise ValueError('Each row needs a description and a unique bank reference to detect duplicate imports safely.')
            fingerprint = hashlib.sha256(f'{account["id"]}|{reference}'.encode()).hexdigest()
            prior = connection.execute('SELECT * FROM book_bank_rows WHERE fingerprint=?', (fingerprint,)).fetchone()
            if prior:
                if (prior['cents'], prior['transaction_date']) != (amount, transaction_date):
                    raise ValueError('A bank reference already exists with a different amount or date.')
                continue
            _open_date(connection, transaction_date, [account['id']])
            connection.execute('INSERT INTO book_bank_rows(account_id,transaction_date,description,cents,reference,fingerprint) VALUES (?,?,?,?,?,?)', (account['id'], transaction_date, description, amount, reference, fingerprint))
            added += 1
    return added


def correct_bank_row(payload):
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM book_bank_rows WHERE id=?',(int(payload.get('bank_row_id',0)),)).fetchone()
        if not row or row['matched_entry_id']:
            raise ValueError('Choose an unmatched imported row; undo its match first if needed.')
        reason = str(payload.get('reason','')).strip()
        description = str(payload.get('description','')).strip()
        reference = str(payload.get('reference','')).strip()
        transaction_date = day(payload.get('date'))
        amount = cents(payload.get('amount'))
        account = _account(connection,payload.get('account_id',row['account_id']))
        if not account['is_bank'] or not reason or not description or not reference or not amount:
            raise ValueError('Provide an account, nonzero amount, description, reference and correction reason.')
        _open_date(connection,row['transaction_date'],[row['account_id']])
        _open_date(connection,transaction_date,[account['id']])
        fingerprint = hashlib.sha256(f'{account["id"]}|{reference}'.encode()).hexdigest()
        connection.execute('INSERT INTO book_bank_row_history(bank_row_id,original_json,reason) VALUES (?,?,?)',(row['id'],json.dumps(dict(row)),reason))
        connection.execute('UPDATE book_bank_rows SET account_id=?,transaction_date=?,description=?,cents=?,reference=?,fingerprint=? WHERE id=?',
            (account['id'],transaction_date,description,amount,reference,fingerprint,row['id']))


def match_bank_row(payload):
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM book_bank_rows WHERE id=?', (int(payload.get('bank_row_id', 0)),)).fetchone()
        entry = connection.execute('''SELECT e.*,t.transaction_date FROM book_entries e JOIN book_transactions t ON t.id=e.transaction_id WHERE e.id=?''', (int(payload.get('entry_id', 0)),)).fetchone()
        if not row or not entry or row['account_id'] != entry['account_id'] or row['cents'] != entry['cents']:
            raise ValueError('Match a statement row to a transaction with the same account and exact amount.')
        if row['matched_entry_id']:
            raise ValueError('This statement row is already matched.')
        _open_date(connection, row['transaction_date'], [row['account_id']])
        connection.execute('UPDATE book_bank_rows SET matched_entry_id=? WHERE id=?', (entry['id'], row['id']))


def unmatch_bank_row(payload):
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT * FROM book_bank_rows WHERE id=?', (int(payload.get('bank_row_id', 0)),)).fetchone()
        if not row:
            raise ValueError('Statement row not found.')
        _open_date(connection, row['transaction_date'], [row['account_id']])
        connection.execute('UPDATE book_bank_rows SET matched_entry_id=NULL WHERE id=?', (row['id'],))


def reconcile(payload):
    end = day(payload.get('end_date'))
    ending = cents(payload.get('ending_balance'))
    if end > date.today().isoformat():
        raise ValueError('Statement end date cannot be in the future.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        account = _account(connection, payload.get('account_id', 0))
        if not account['is_bank']:
            raise ValueError('Choose a bank or card account.')
        _open_date(connection, end, [account['id']])
        if account['kind'] == 'liability':
            ending = -ending
        bad = connection.execute('SELECT COUNT(*) AS count FROM book_bank_rows WHERE account_id=? AND transaction_date<=? AND matched_entry_id IS NULL', (account['id'], end)).fetchone()['count']
        if bad:
            raise ValueError('Match all imported statement rows through the statement end date first.')
        future = connection.execute('''SELECT COUNT(*) AS count FROM book_bank_rows b JOIN book_entries e ON e.id=b.matched_entry_id JOIN book_transactions t ON t.id=e.transaction_id
            WHERE b.account_id=? AND b.transaction_date<=? AND t.transaction_date>?''', (account['id'], end, end)).fetchone()['count']
        if future:
            raise ValueError('A matched book transaction is dated after this statement. Correct the date with a reversal and repost.')
        balance = connection.execute('''SELECT COALESCE(SUM(e.cents),0) AS balance FROM book_entries e JOIN book_transactions t ON t.id=e.transaction_id
            WHERE e.account_id=? AND t.transaction_date<=? AND (t.kind='opening' OR EXISTS
            (SELECT 1 FROM book_bank_rows b WHERE b.matched_entry_id=e.id AND b.transaction_date<=?))''', (account['id'], end, end)).fetchone()['balance']
        if balance != ending:
            raise ValueError(f'Statement does not balance: cleared book balance {money(-balance if account["kind"] == "liability" else balance)}. Difference {money(ending-balance)}.')
        connection.execute('INSERT INTO book_reconciliations(account_id,end_date,ending_cents) VALUES (?,?,?)', (account['id'], end, ending))


def close_period(payload):
    end = day(payload.get('end_date'))
    if end > date.today().isoformat():
        raise ValueError('Do not close a future period.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        _open_date(connection, end)
        accounts = connection.execute('SELECT id FROM book_accounts WHERE is_bank=1').fetchall()
        if not accounts:
            raise ValueError('Set up and reconcile the business accounts first.')
        for account in accounts:
            last = connection.execute('SELECT MAX(end_date) AS end_date FROM book_reconciliations WHERE account_id=?', (account['id'],)).fetchone()['end_date']
            if not last or last < end:
                raise ValueError('Reconcile every bank/card account through the close date first.')
        connection.execute("INSERT OR REPLACE INTO book_settings(key,value) VALUES ('closed_through',?)", (end,))


def review_expense(payload):
    treatments = {'operating', 'already_in_order_cost', 'inventory_purchase', 'equipment', 'owner_draw', 'loan_principal', 'transfer', 'unreviewed'}
    treatment = payload.get('treatment')
    if treatment not in treatments:
        raise ValueError('Choose an expense treatment.')
    note = str(payload.get('note', '')).strip()
    if treatment != 'unreviewed' and not note:
        raise ValueError('Add a note explaining the classification so your CPA can review it.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        expense = connection.execute('SELECT expense_date FROM expenses WHERE id=?', (int(payload.get('expense_id', 0)),)).fetchone()
        if not expense:
            raise ValueError('Expense not found.')
        _open_date(connection, expense['expense_date'])
        connection.execute('''INSERT INTO expense_treatments(expense_id,treatment,note) VALUES (?,?,?)
            ON CONFLICT(expense_id) DO UPDATE SET treatment=excluded.treatment,note=excluded.note,reviewed_at=CURRENT_TIMESTAMP''', (payload['expense_id'], treatment, note))


def review_loss(payload):
    treatment = payload.get('treatment')
    note = str(payload.get('note', '')).strip()
    if treatment not in {'unreviewed','additional_writeoff','already_in_order_cost','inventory_adjustment'}:
        raise ValueError('Choose a write-off treatment.')
    if treatment != 'unreviewed' and not note:
        raise ValueError('Explain the classification for CPA review.')
    with create_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        loss = connection.execute('SELECT loss_date FROM losses WHERE id=?', (int(payload.get('loss_id',0)),)).fetchone()
        if not loss:
            raise ValueError('Write-off not found.')
        _open_date(connection, loss['loss_date'])
        connection.execute("""INSERT INTO loss_treatments(loss_id,treatment,note) VALUES (?,?,?) ON CONFLICT(loss_id)
            DO UPDATE SET treatment=excluded.treatment,note=excluded.note,reviewed_at=CURRENT_TIMESTAMP""", (payload['loss_id'],treatment,note))


def operating_losses(losses):
    with create_connection() as connection:
        excluded = {row['loss_id'] for row in connection.execute("SELECT loss_id FROM loss_treatments WHERE treatment IN ('already_in_order_cost','inventory_adjustment')")}
    return [loss for loss in losses if loss.id not in excluded]


def operating_expenses(expenses):
    with create_connection() as connection:
        excluded = {row['expense_id'] for row in connection.execute("SELECT expense_id FROM expense_treatments WHERE treatment NOT IN ('operating','unreviewed')")}
    return [expense for expense in expenses if expense.id not in excluded]


def workspace(start=None, end=None):
    end = day(end or date.today().isoformat())
    start = day(start) if start else date.today().replace(month=1, day=1).isoformat()
    if start > end:
        raise ValueError('Start date must not be after end date.')
    with create_connection() as connection:
        accounts = []
        for account in connection.execute('SELECT * FROM book_accounts ORDER BY is_bank DESC,id'):
            amount = connection.execute('SELECT COALESCE(SUM(e.cents),0) AS cents FROM book_entries e JOIN book_transactions t ON t.id=e.transaction_id WHERE e.account_id=? AND t.transaction_date<=?', (account['id'], end)).fetchone()['cents']
            accounts.append(dict(account, balance=money(amount), displayed_balance=money(-amount if account['kind'] in {'liability','equity','income'} else amount)))
        entries = [dict(row, amount=money(row['cents'])) for row in connection.execute('''SELECT e.id AS entry_id,e.transaction_id,e.account_id,e.cents,a.name AS account,a.kind AS account_kind,a.code,a.is_bank,
            t.transaction_date,t.kind,t.description,t.reference,t.order_id,t.expense_id,t.document_id,t.reversed_id,t.created_at,t.source_snapshot,(SELECT kind FROM book_transactions original WHERE original.id=t.reversed_id) AS original_kind,
            (SELECT id FROM book_bank_rows b WHERE b.matched_entry_id=e.id) AS bank_row_id
            FROM book_entries e JOIN book_transactions t ON t.id=e.transaction_id JOIN book_accounts a ON a.id=e.account_id
            WHERE t.transaction_date BETWEEN ? AND ? ORDER BY t.transaction_date DESC,t.id DESC,e.id''', (start, end))]
        bank_rows = [dict(row, amount=money(row['cents'])) for row in connection.execute('SELECT * FROM book_bank_rows WHERE transaction_date BETWEEN ? AND ? ORDER BY transaction_date DESC,id DESC', (start, end))]
        bank_corrections = [dict(row) for row in connection.execute('SELECT * FROM book_bank_row_history ORDER BY id DESC')]
        reconciliations = [dict(row, ending_balance=money(row['ending_cents'])) for row in connection.execute('SELECT r.*,a.name AS account FROM book_reconciliations r JOIN book_accounts a ON a.id=r.account_id ORDER BY end_date DESC')]
        documents = [dict(row) for row in connection.execute("SELECT id, file_path, description FROM documents ORDER BY id DESC LIMIT 500")]
        expenses = [dict(row) for row in connection.execute('''SELECT e.id,e.category,e.amount,e.expense_date,e.description,e.material_id,e.document_id,
            COALESCE(t.treatment,'unreviewed') AS treatment,COALESCE(t.note,'') AS review_note,
            (SELECT id FROM book_transactions b WHERE b.expense_id=e.id LIMIT 1) AS book_transaction_id
            FROM expenses e LEFT JOIN expense_treatments t ON t.expense_id=e.id WHERE expense_date BETWEEN ? AND ? ORDER BY expense_date DESC,e.id DESC''', (start, end))]
        losses = [dict(row) for row in connection.execute("""SELECT l.id,l.category,l.amount,l.loss_date AS expense_date,l.description,
            COALESCE(t.treatment,'unreviewed') AS treatment,COALESCE(t.note,'') AS review_note,NULL AS book_transaction_id
            FROM losses l LEFT JOIN loss_treatments t ON t.loss_id=l.id WHERE l.loss_date BETWEEN ? AND ? ORDER BY l.loss_date DESC,l.id DESC""", (start,end))]
        closed = connection.execute("SELECT value FROM book_settings WHERE key='closed_through'").fetchone()
        orders = [dict(row) for row in connection.execute('''SELECT o.id,o.order_number,o.customer_name,o.status,o.deleted_at,o.total_amount,
            CASE WHEN o.is_paid=1 THEN o.total_amount + CASE WHEN o.tax_included_in_total=1 THEN o.tax_amount ELSE 0 END ELSE COALESCE(w.amount_paid,0) END AS legacy_paid
            FROM orders o LEFT JOIN order_workflow w ON w.order_id=o.id ORDER BY o.order_date DESC,o.id DESC''')]
    income = -sum(row['cents'] for row in entries if row['account_kind']=='income')
    expense = sum(row['cents'] for row in entries if row['account_kind']=='expense')
    assets = sum(cents(account['balance']) for account in accounts if account['kind']=='asset')
    liabilities = -sum(cents(account['balance']) for account in accounts if account['kind']=='liability')
    equity = -sum(cents(account['balance']) for account in accounts if account['kind']=='equity')
    # Retained earnings uses lifetime income/expenses, not just the selected period.
    lifetime_profit = -sum(cents(account['balance']) for account in accounts if account['kind'] in {'income','expense'})
    return dict(period=dict(start=start,end=end), accounts=accounts, entries=entries, bank_rows=bank_rows,
        reconciliations=reconciliations, bank_corrections=bank_corrections, expenses=expenses, losses=losses, orders=orders, documents=documents, closed_through=closed['value'] if closed else None,
        metrics=dict(income=money(income), expenses=money(expense), net_profit=money(income-expense), assets=money(assets),
            liabilities=money(liabilities), equity=money(equity+lifetime_profit), balance_check=money(assets-liabilities-equity-lifetime_profit)),
        notes='Books use explicitly dated postings only. Historical order payment flags are not imported. Order performance and books are separate views; never add their totals together. Opening balances require CPA review. Statement imports are matched to postings, not counted as additional income or spending.')
