from __future__ import annotations
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from hustlenest.data.database import initialize, create_connection
from hustlenest.services import bookkeeping_service as books, finance_service, order_service
from hustlenest.data import order_repository, expense_repository
from hustlenest.models.order_models import Order, OrderItem, Expense, OrderReportRow


class BookkeepingTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'LOCALAPPDATA': self.storage.name})
        self.environment.start()
        initialize()
        self.today = date.today().isoformat()
        self.account = books.create_account({'name':'Checking','kind':'asset','opening_balance':'0'})

    def tearDown(self):
        from hustlenest.data.database import close_database_for_replacement
        close_database_for_replacement()
        self.environment.stop()
        self.storage.cleanup()

    def post(self, kind, amount, **extra):
        return books.post_transaction(dict(date=self.today, kind=kind, amount=amount, account_id=self.account,
            description='Test '+kind, **extra))

    def snapshot(self):
        return books.workspace(self.today, self.today)

    def test_exact_cents_and_invalid_inputs(self):
        for value in ['NaN','Infinity','1.005',True]:
            with self.assertRaises(ValueError): books.cents(value)
        self.assertEqual(books.cents('0.29'),29)
        with self.assertRaises(ValueError): self.post('receipt',0)
        with self.assertRaises(ValueError): self.post('receipt',10,sales_tax=11)
        with self.assertRaises(ValueError): self.post('receipt',10,processing_fee=10)

    def test_receipt_splits_tax_and_fees_and_balances(self):
        self.post('receipt','110',sales_tax='10',processing_fee='3')
        state=self.snapshot()
        self.assertEqual(state['metrics']['income'],'100.00')
        self.assertEqual(state['metrics']['expenses'],'3.00')
        self.assertEqual(state['metrics']['net_profit'],'97.00')
        self.assertEqual(state['metrics']['assets'],'107.00')
        self.assertEqual(state['metrics']['liabilities'],'10.00')
        self.assertEqual(state['metrics']['balance_check'],'0.00')
        self.assertEqual(sum(row['cents'] for row in state['entries']),0)

    def test_refund_reduces_income_and_tax(self):
        self.post('receipt',110,sales_tax=10)
        self.post('refund',55,sales_tax=5)
        state=self.snapshot()
        self.assertEqual(state['metrics']['income'],'50.00')
        self.assertEqual(state['metrics']['liabilities'],'5.00')
        self.assertEqual(state['metrics']['assets'],'55.00')

    def test_inventory_purchase_only_expensed_when_used(self):
        self.post('owner_contribution',200)
        self.post('inventory_purchase',60)
        self.assertEqual(self.snapshot()['metrics']['expenses'],'0.00')
        self.post('inventory_used',40)
        self.assertEqual(self.snapshot()['metrics']['expenses'],'40.00')
        self.assertEqual(self.snapshot()['metrics']['balance_check'],'0.00')

    def test_owner_loan_equipment_transfer_not_operating_expenses(self):
        second=books.create_account({'name':'Savings','kind':'asset'})
        self.post('owner_contribution',200)
        self.post('loan_received',100)
        self.post('owner_draw',20)
        self.post('loan_principal_payment',10)
        self.post('equipment_purchase',50)
        self.post('transfer',30,target_account_id=second)
        self.assertEqual(self.snapshot()['metrics']['net_profit'],'0.00')
        self.assertEqual(self.snapshot()['metrics']['balance_check'],'0.00')

    def test_repeated_request_is_not_posted_twice(self):
        first=self.post('receipt',20,request_id='stable-request')
        second=self.post('receipt',20,request_id='stable-request')
        self.assertEqual(first,second)
        self.assertEqual(self.snapshot()['metrics']['income'],'20.00')

    def test_bank_import_deduplicates_and_rejects_changed_reference(self):
        data={'account_id':self.account,'rows':[dict(date=self.today,description='Payment',amount='20',reference='BANK-1')]}
        self.assertEqual(books.import_bank_rows(data),1)
        self.assertEqual(books.import_bank_rows(data),0)
        data['rows'][0]['amount']='21'
        with self.assertRaises(ValueError): books.import_bank_rows(data)
        self.assertEqual(len(self.snapshot()['bank_rows']),1)
        self.assertEqual(self.snapshot()['metrics']['income'],'0.00')

    def test_csv_import_and_matching_are_not_additional_income(self):
        self.post('receipt',20)
        books.import_bank_rows({'account_id':self.account,'csv_text':f'date,description,amount,reference\n{self.today},"Payment, customer",20.00,BANK-1\n'})
        state=self.snapshot();row=state['bank_rows'][0];entry=next(e for e in state['entries'] if e['is_bank'])
        books.match_bank_row({'bank_row_id':row['id'],'entry_id':entry['entry_id']})
        self.assertEqual(self.snapshot()['metrics']['income'],'20.00')
        books.unmatch_bank_row({'bank_row_id':row['id']})
        self.assertIsNone(self.snapshot()['bank_rows'][0]['matched_entry_id'])

    def test_reconcile_requires_match_and_exact_balance_then_protects_history(self):
        self.post('receipt',20)
        books.import_bank_rows({'account_id':self.account,'rows':[dict(date=self.today,description='Payment',amount=20,reference='1')]})
        data={'account_id':self.account,'end_date':self.today,'ending_balance':20}
        with self.assertRaises(ValueError): books.reconcile(data)
        state=self.snapshot();row=state['bank_rows'][0];entry=next(e for e in state['entries'] if e['is_bank'])
        books.match_bank_row({'bank_row_id':row['id'],'entry_id':entry['entry_id']})
        with self.assertRaises(ValueError): books.reconcile(dict(data,ending_balance=21))
        books.reconcile(data)
        with self.assertRaises(ValueError): self.post('receipt',10)
        with self.assertRaises(ValueError): books.unmatch_bank_row({'bank_row_id':row['id']})
        books.close_period({'end_date':self.today})
        self.assertEqual(self.snapshot()['closed_through'],self.today)

    def test_wrong_account_or_amount_cannot_match(self):
        self.post('receipt',20)
        books.import_bank_rows({'account_id':self.account,'rows':[dict(date=self.today,description='Payment',amount=21,reference='1')]})
        state=self.snapshot()
        with self.assertRaises(ValueError): books.match_bank_row({'bank_row_id':state['bank_rows'][0]['id'],'entry_id':next(e for e in state['entries'] if e['is_bank'])['entry_id']})

    def test_opening_balance_and_card_signs(self):
        card=books.create_account({'name':'Card','kind':'liability','opening_balance':100,'opening_date':self.today})
        self.post('expense',20,**{})
        books.post_transaction(dict(date=self.today,kind='expense',amount=50,account_id=card,description='Card purchase'))
        state=self.snapshot()
        self.assertEqual(next(a for a in state['accounts'] if a['id']==card)['displayed_balance'],'150.00')
        self.assertEqual(state['metrics']['balance_check'],'0.00')

    def test_reversal_keeps_original_and_cannot_be_repeated(self):
        tx=self.post('receipt',20)
        books.reverse_transaction({'transaction_id':tx,'date':self.today,'description':'Wrong amount'})
        self.assertEqual(self.snapshot()['metrics']['income'],'0.00')
        self.assertEqual(len(self.snapshot()['entries']),4)
        with self.assertRaises(ValueError): books.reverse_transaction({'transaction_id':tx,'date':self.today,'description':'Again'})

    def test_cancelled_or_trashed_order_does_not_erase_real_cash(self):
        oid=order_repository.insert_order(Order(order_number='A',customer_name='Customer',customer_address='',order_date=date.today(),status='Received',items=[OrderItem('Hat','',1,20,'H')]))
        self.post('receipt',20,order_id=oid)
        with create_connection() as c: c.execute("UPDATE orders SET status='Cancelled',deleted_at=? WHERE id=?",(self.today,oid))
        self.assertEqual(order_repository.fetch_order_report(None,date.today()),[])
        self.assertEqual(self.snapshot()['metrics']['income'],'20.00')
        self.post('refund',20,order_id=oid)
        self.assertEqual(self.snapshot()['metrics']['income'],'0.00')

    def test_expense_review_prevents_double_deduction(self):
        eid=expense_repository.save_expense(Expense(None,'Blank hats',60,date.today()))
        self.assertEqual(finance_service.calculate_expense_total(),60)
        books.review_expense({'expense_id':eid,'treatment':'already_in_order_cost','note':'Included in order H-1'})
        self.assertEqual(finance_service.calculate_expense_total(),0)
        self.assertEqual(self.snapshot()['expenses'][0]['treatment'],'already_in_order_cost')
        self.post('inventory_purchase',60,expense_id=eid)
        with self.assertRaises(ValueError): self.post('expense',60,expense_id=eid)

    def test_zero_sale_reduces_profit_not_revenue(self):
        o=Order('ZERO','Customer','',date.today(),'Shipped',items=[OrderItem('Original','',12,17,'A',base_unit_cost=5),OrderItem('Replacement','',12,0,'B',base_unit_cost=5,is_freebie=True)])
        order_repository.insert_order(o)
        row=order_repository.fetch_order_report(None,date.today())[0]
        self.assertEqual(row.total_amount,204)
        self.assertEqual(row.net_revenue,204)
        self.assertEqual(row.profit,84)
        snap=order_repository.build_dashboard_snapshot()
        self.assertEqual(snap.net_sales,204)
        self.assertAlmostEqual(snap.profit_margin,84/204)

    def test_partial_receipt_not_double_counted_in_outlook(self):
        oid=order_repository.insert_order(Order('PART','Customer','',date.today(),'Received',items=[OrderItem('Hat','',1,100,'H')]))
        self.post('receipt',40,order_id=oid)
        flow=finance_service.summarize_cash_flow()
        self.assertEqual(flow.sales_realized,40)
        self.assertEqual(flow.receivables,60)
        self.assertEqual(flow.net_projection,100)

    def test_linked_new_payment_updates_order_without_counting_twice(self):
        oid=order_repository.insert_order(Order('SYNC','Customer','',date.today(),'Received',items=[OrderItem('Hat','',1,100,'H')]))
        self.post('receipt',40,order_id=oid,update_order_payment=True,request_id='sync-1')
        self.post('receipt',40,order_id=oid,update_order_payment=True,request_id='sync-1')
        with create_connection() as c:
            self.assertEqual(c.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?',(oid,)).fetchone()['amount_paid'],40)
        self.assertEqual(finance_service.summarize_cash_flow().receivables,60)
        self.post('refund',10,order_id=oid,update_order_payment=True)
        with create_connection() as c:
            self.assertEqual(c.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?',(oid,)).fetchone()['amount_paid'],30)

    def test_journal_adjustment_and_immutable_entries(self):
        import sqlite3
        state=self.snapshot()
        inventory=next(a['id'] for a in state['accounts'] if a['code']=='inventory')
        equity=next(a['id'] for a in state['accounts'] if a['code']=='capital')
        books.post_adjustment(dict(date=self.today,amount=100,debit_account_id=inventory,credit_account_id=equity,description='CPA opening inventory'))
        self.assertEqual(self.snapshot()['metrics']['assets'],'100.00')
        self.assertEqual(self.snapshot()['metrics']['net_profit'],'0.00')
        with self.assertRaises(sqlite3.IntegrityError):
            with create_connection() as c: c.execute('DELETE FROM book_entries')

    def test_source_snapshot_survives_order_removal(self):
        import json
        oid=order_repository.insert_order(Order('SOURCE','Customer','',date.today(),'Received',items=[OrderItem('Hat','',1,20,'H')]))
        self.post('receipt',20,order_id=oid)
        order_repository.delete_order(oid)
        source=json.loads(self.snapshot()['entries'][0]['source_snapshot'])
        self.assertEqual(source['order_id']['order_number'],'SOURCE')
        self.assertEqual(self.snapshot()['metrics']['income'],'20.00')

    def test_books_routes_and_validation(self):
        from hustlenest.web_bridge import BridgeApplication,BridgeError
        api=BridgeApplication()
        status,state=api.dispatch('GET','/api/books')
        self.assertEqual(status,200)
        self.assertIn('balance_check',state['metrics'])
        with self.assertRaises(BridgeError):
            api.dispatch('POST','/api/books/transactions',{'kind':'receipt','amount':'1.001','date':self.today})

    def test_writeoff_classification_avoids_second_deduction(self):
        from hustlenest.models.order_models import LossRecord
        from hustlenest.data import loss_repository
        lid=loss_repository.create_loss(LossRecord(None,60,date.today(),'Remake'))
        self.assertEqual(finance_service.calculate_loss_total(),60)
        books.review_loss({'loss_id':lid,'treatment':'already_in_order_cost','note':'Included in order costs'})
        self.assertEqual(finance_service.calculate_loss_total(),0)
        self.assertEqual(self.snapshot()['losses'][0]['treatment'],'already_in_order_cost')

    def test_cpa_exports_book_entries_and_classifications(self):
        import io,zipfile
        from hustlenest.web_bridge import report_download
        self.post('receipt',20)
        download=report_download({'kind':['cpa_zip'],'period':['this_year'],
            'include':['books_csv','accounts_csv','bank_csv','reconciliations_csv','expense_review_csv','loss_review_csv']})
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            self.assertIn('book_entries.csv',archive.namelist())
            self.assertIn('source_snapshot',archive.read('book_entries.csv').decode('utf-8-sig'))
            self.assertNotIn('orders.csv',archive.namelist())
            self.assertIn('writeoff_classification.csv',archive.namelist())

    def test_reversal_restores_order_paid_balance_and_cash_outlook(self):
        oid=order_repository.insert_order(Order('UNDO','Customer','',date.today(),'Received',items=[OrderItem('Hat','',1,100,'H')]))
        tx=self.post('receipt',40,order_id=oid,update_order_payment=True)
        books.reverse_transaction({'transaction_id':tx,'date':self.today,'description':'Incorrect payment'})
        flow=finance_service.summarize_cash_flow()
        self.assertEqual(flow.sales_realized,0)
        self.assertEqual(flow.receivables,100)
        with create_connection() as c:
            self.assertEqual(c.execute('SELECT amount_paid FROM order_workflow WHERE order_id=?',(oid,)).fetchone()['amount_paid'],0)

    def test_import_correction_preserves_original_and_reason(self):
        books.import_bank_rows({'account_id':self.account,'rows':[dict(date=self.today,description='Wrong',amount=21,reference='1')]})
        row=self.snapshot()['bank_rows'][0]
        books.correct_bank_row(dict(bank_row_id=row['id'],date=self.today,amount=20,description='Corrected',reference='1',reason='CSV amount typo'))
        state=self.snapshot()
        self.assertEqual(state['bank_rows'][0]['amount'],'20.00')
        self.assertEqual(state['bank_corrections'][0]['reason'],'CSV amount typo')
        self.assertIn('2100',state['bank_corrections'][0]['original_json'])

    def test_closed_period_requires_all_accounts_reconciled(self):
        with self.assertRaises(ValueError): books.close_period({'end_date':self.today})

    def test_entries_roll_back_together_on_error(self):
        with self.assertRaises(ValueError): self.post('receipt',20,order_id=99999)
        self.assertEqual(self.snapshot()['entries'],[])

if __name__ == '__main__': unittest.main()
