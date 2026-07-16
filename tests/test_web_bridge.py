from __future__ import annotations

import os
import base64
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from hustlenest.data import (
    crm_repository,
    document_repository,
    expense_repository,
    goal_repository,
    loss_repository,
    material_repository,
    order_repository,
    product_repository,
    settings_repository,
    vendor_repository,
)
from hustlenest.data.database import close_database_for_replacement, initialize
from hustlenest.models.order_models import (
    CRMContact,
    CostComponent,
    DocumentRecord,
    BusinessGoal,
    Expense,
    Material,
    MaterialTransaction,
    LossRecord,
    Order,
    OrderItem,
    RecurringExpense,
    Vendor,
)
from hustlenest.web_bridge import BinaryDownload, BridgeApplication, BridgeError
from hustlenest import browser_launcher
from hustlenest.services import order_service, soft_delete_service


class OrdersBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": self.storage.name})
        self.environment.start()
        initialize()
        self.product = product_repository.create_product("TEST-001", "Test Product", mark_complete=True)
        self.product.inventory_count = 10
        self.product.default_unit_price = 12.5
        self.product.base_unit_cost = 4.0
        self.product = product_repository.update_product(self.product)
        crm_repository.save_contact(
            CRMContact(
                id=None,
                customer_name="Test Customer",
                email="customer@example.com",
                phone="555-0100",
                address="100 Market Street\nSpringfield, MO 65806",
            )
        )
        self.order_id = order_repository.insert_order(
            Order(
                order_number="HN-TEST-001",
                customer_name="Test Customer",
                customer_address="100 Market Street\nSpringfield, MO 65806",
                order_date=date.today(),
                target_completion_date=date.today() - timedelta(days=1),
                status="Received",
                notes="Bridge integration order",
                items=[
                    OrderItem(
                        product_name="Test Product",
                        product_description="Fixture item",
                        product_sku="TEST-001",
                        product_id=self.product.id,
                        quantity=2,
                        unit_price=12.5,
                        base_unit_cost=4.0,
                    )
                ],
            )
        )
        self.application = BridgeApplication()

    def tearDown(self) -> None:
        close_database_for_replacement()
        self.environment.stop()
        self.storage.cleanup()

    def test_lists_repository_orders_using_bridge_dtos(self) -> None:
        status, payload = self.application.dispatch("GET", "/api/orders?limit=10")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["number"], "HN-TEST-001")
        self.assertEqual(payload[0]["total"], "25.00")
        self.assertEqual(payload[0]["items"][0]["line_profit"], "17.00")
        self.assertIn("overdue", payload[0]["attention_reasons"])

    def test_metrics_and_guarded_status_advancement(self) -> None:
        status, metrics = self.application.dispatch("GET", "/api/orders/metrics")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(metrics["open_orders"], 1)
        self.assertEqual(metrics["awaiting_payment"], "25.00")

        status, updated = self.application.dispatch(
            "POST",
            f"/api/orders/{self.order_id}/advance",
            {"expected_status": "Received"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["status"], "Paid")
        self.assertEqual(updated["payment_status"], "paid")

        with self.assertRaisesRegex(BridgeError, "another window"):
            self.application.dispatch(
                "POST",
                f"/api/orders/{self.order_id}/advance",
                {"expected_status": "Received"},
            )

    def test_browser_history_filters_events_and_embeds_order_activity(self) -> None:
        order_repository.log_order_event(self.order_id, "HN-TEST-001", "Created", "Order created for audit test.", 25)
        order_repository.log_order_event(self.order_id, "HN-TEST-001", "Payment changed", "Payment recorded.", 0)
        order_repository.log_order_event(None, "HN-OTHER-999", "Deleted", "Historical order removed.", -10)

        status, history = self.application.dispatch(
            "GET",
            "/api/history?query=TEST&limit=50",
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(history["metrics"]["total"], 2)
        self.assertEqual(history["metrics"]["orders"], 1)
        self.assertEqual(history["metrics"]["net_change"], "25.00")
        self.assertTrue(all(event["order_available"] for event in history["events"]))
        self.assertEqual({item["name"] for item in history["event_types"]}, {"Created", "Payment changed"})

        status, order = self.application.dispatch("GET", f"/api/orders/{self.order_id}")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(len(order["activity"]), 2)
        self.assertEqual(order["activity"][0]["event_type"], "Payment changed")

        with self.assertRaisesRegex(BridgeError, "End date cannot"):
            self.application.dispatch("GET", "/api/history?start_date=2026-07-20&end_date=2026-07-01")

    def test_browser_payment_invoice_and_cancellation_lifecycle(self) -> None:
        status, paid = self.application.dispatch(
            "POST",
            f"/api/orders/{self.order_id}/payment",
            {"expected_payment_status": "unpaid", "payment_status": "paid"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(paid["payment_status"], "paid")
        _, metrics = self.application.dispatch("GET", "/api/orders/metrics")
        self.assertEqual(metrics["awaiting_payment_count"], 0)

        with self.assertRaises(BridgeError) as payment_conflict:
            self.application.dispatch(
                "POST",
                f"/api/orders/{self.order_id}/payment",
                {"expected_payment_status": "unpaid", "payment_status": "paid"},
            )
        self.assertEqual(payment_conflict.exception.code, "payment_conflict")

        order_service.ensure_invoice_runtime()
        with ThreadPoolExecutor(max_workers=1) as executor:
            invoice_status, invoice = executor.submit(self.application.dispatch, "GET", f"/api/orders/{self.order_id}/invoice").result()
        self.assertEqual(invoice_status, HTTPStatus.OK)
        self.assertIsInstance(invoice, BinaryDownload)
        self.assertEqual(invoice.content_type, "application/pdf")
        self.assertEqual(invoice.filename, "HN-TEST-001_receipt.pdf")
        self.assertTrue(invoice.content.startswith(b"%PDF"))
        self.assertGreater(len(invoice.content), 1000)

        inventory_before = product_repository.get_product_by_id(self.product.id).inventory_count
        cancel_status, cancelled = self.application.dispatch(
            "POST",
            f"/api/orders/{self.order_id}/cancel",
            {"expected_status": "Received"},
        )
        self.assertEqual(cancel_status, HTTPStatus.OK)
        self.assertEqual(cancelled["status"], "Cancelled")
        self.assertEqual(product_repository.get_product_by_id(self.product.id).inventory_count, inventory_before + 2)
        _, metrics = self.application.dispatch("GET", "/api/orders/metrics")
        self.assertEqual(metrics["open_orders"], 0)
        self.assertEqual(metrics["awaiting_payment_count"], 0)

        with self.assertRaises(BridgeError) as stale_cancel:
            self.application.dispatch(
                "POST",
                f"/api/orders/{self.order_id}/cancel",
                {"expected_status": "Received"},
            )
        self.assertEqual(stale_cancel.exception.code, "status_conflict")

    def test_lookup_create_and_update_order_workflow(self) -> None:
        _, customers = self.application.dispatch("GET", "/api/customers?query=customer")
        _, products = self.application.dispatch("GET", "/api/products?query=test")
        _, options = self.application.dispatch("GET", "/api/order-options")
        self.assertEqual(customers[0]["email"], "customer@example.com")
        self.assertEqual(products[0]["sku"], "TEST-001")
        self.assertEqual(options["next_order_number"], "ORD-0001")

        draft = {
            "customer": {
                "name": "Browser Customer",
                "address": "200 Main Street, Springfield, MO 65806",
            },
            "order_date": date.today().isoformat(),
            "target_completion_date": (date.today() + timedelta(days=5)).isoformat(),
            "status": "Received",
            "payment_status": "unpaid",
            "items": [
                {"product_id": self.product.id, "quantity": 2, "unit_price": "15.00"}
            ],
            "notes": "Created in browser test",
        }
        status, created = self.application.dispatch("POST", "/api/orders", draft)
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(created["number"], "ORD-0001")
        self.assertEqual(created["total"], "30.00")
        self.assertIsNotNone(created["customer_id"])
        self.assertEqual(product_repository.get_product_by_id(self.product.id).inventory_count, 8)

        draft["expected_status"] = "Received"
        draft["payment_status"] = "paid"
        draft["notes"] = "Updated in browser test"
        draft["items"][0]["quantity"] = 3
        status, updated = self.application.dispatch("PUT", f"/api/orders/{created['id']}", draft)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["payment_status"], "paid")
        self.assertEqual(updated["notes"], "Updated in browser test")
        self.assertEqual(product_repository.get_product_by_id(self.product.id).inventory_count, 7)

    def test_create_validation_returns_stable_field_codes(self) -> None:
        with self.assertRaises(BridgeError) as raised:
            self.application.dispatch("POST", "/api/orders", {})

        self.assertEqual(raised.exception.code, "validation_failed")
        self.assertEqual(raised.exception.fields["customer.name"], "required")
        self.assertEqual(raised.exception.fields["customer.address"], "required")
        self.assertEqual(raised.exception.fields["items"], "required")
        _, options = self.application.dispatch("GET", "/api/order-options")
        self.assertEqual(options["next_order_number"], "ORD-0001")

    def test_customers_include_names_that_exist_only_on_orders(self) -> None:
        order_repository.insert_order(
            Order(
                order_number="HN-ORDER-CUSTOMER",
                customer_name="Klay Cox",
                customer_address="Saltillo, MS",
                order_date=date.today(),
                status="Shipped",
                is_paid=True,
                items=[
                    OrderItem(
                        product_name="Test Product",
                        product_description="",
                        product_sku="TEST-001",
                        product_id=self.product.id,
                        quantity=1,
                        unit_price=12.5,
                    )
                ],
            )
        )

        status, customers = self.application.dispatch("GET", "/api/customers?query=Klay")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["name"], "Klay Cox")
        self.assertIsNone(customers[0]["id"])
        self.assertEqual(customers[0]["address"], "Saltillo, MS")

    def test_browser_logs_customer_interactions_and_updates_followup_cadence(self) -> None:
        _, customers = self.application.dispatch("GET", "/api/customers?query=Test%20Customer")
        customer = customers[0]
        follow_up = date.today() + timedelta(days=3)
        status, detail = self.application.dispatch(
            "POST",
            f"/api/customers/{customer['id']}/interactions",
            {
                "expected_revision": customer["revision"],
                "values": {
                    "interaction_date": date.today().isoformat(),
                    "channel": "Email",
                    "summary": "Confirmed the delivery timeline.",
                    "follow_up_date": follow_up.isoformat(),
                    "follow_up_action": "Send tracking details",
                    "order_id": self.order_id,
                },
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(detail["last_contacted"], date.today().isoformat())
        self.assertEqual(detail["next_follow_up"], follow_up.isoformat())
        self.assertEqual(detail["preferred_channel"], "Email")
        self.assertEqual(detail["interactions"][0]["summary"], "Confirmed the delivery timeline.")
        self.assertEqual(detail["interactions"][0]["order_id"], self.order_id)
        saved = crm_repository.get_contact(customer["id"])
        self.assertEqual(saved.next_follow_up, follow_up)

        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch(
                "POST",
                f"/api/customers/{customer['id']}/interactions",
                {"expected_revision": customer["revision"], "values": {"interaction_date": date.today().isoformat(), "summary": "Stale entry"}},
            )
        self.assertEqual(stale.exception.code, "record_conflict")

        with self.assertRaises(BridgeError) as invalid_date:
            self.application.dispatch(
                "POST",
                f"/api/customers/{customer['id']}/interactions",
                {"expected_revision": detail["revision"], "values": {"interaction_date": date.today().isoformat(), "summary": "Invalid follow-up", "follow_up_date": (date.today() - timedelta(days=1)).isoformat()}},
            )
        self.assertEqual(invalid_date.exception.fields["follow_up_date"], "before_interaction")

    def test_materials_include_vendor_stock_state_and_transactions(self) -> None:
        vendor_id = vendor_repository.save_vendor(Vendor(id=None, name="Material Supply Co."))
        material_id = material_repository.save_material(
            Material(
                id=None,
                sku="MAT-001",
                name="Walnut blanks",
                category="Wood",
                unit_of_measure="piece",
                quantity_on_hand=4,
                reorder_point=5,
                cost_per_unit=3.25,
                vendor_id=vendor_id,
                lead_time_days=7,
            )
        )
        material_repository.record_transaction(
            MaterialTransaction(
                id=None,
                material_id=material_id,
                transaction_date=datetime.now(),
                quantity_delta=4,
                unit_cost=3.25,
                reason="Initial stock",
            )
        )

        status, materials = self.application.dispatch("GET", "/api/materials?query=walnut")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(materials[0]["vendor"]["name"], "Material Supply Co.")
        self.assertEqual(materials[0]["stock_status"], "reorder")
        self.assertEqual(materials[0]["inventory_value"], "13.00")

        status, detail = self.application.dispatch("GET", f"/api/materials/{material_id}")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(detail["transactions"][0]["reason"], "Initial stock")

        status, vendors = self.application.dispatch("GET", "/api/vendors?query=Supply")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(vendors[0]["material_count"], 1)
        self.assertEqual(vendors[0]["inventory_value"], "13.00")
        self.assertEqual(vendors[0]["reorder_count"], 1)

        status, vendor_detail = self.application.dispatch("GET", f"/api/vendors/{vendor_id}")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(vendor_detail["materials"][0]["sku"], "MAT-001")

    def test_browser_material_adjustments_update_stock_and_audit_history(self) -> None:
        material_id = material_repository.save_material(
            Material(id=None, sku="ADJ-001", name="Packing paper", unit_of_measure="sheet", quantity_on_hand=4, cost_per_unit=0.25)
        )
        _, detail = self.application.dispatch("GET", f"/api/materials/{material_id}")
        original_revision = detail["revision"]

        status, received = self.application.dispatch(
            "POST",
            f"/api/materials/{material_id}/adjust",
            {"expected_revision": original_revision, "values": {"action": "receive", "quantity": 6, "unit_cost": 0.2, "notes": "PO 104"}},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(received["quantity_on_hand"], 10)
        self.assertEqual(received["transactions"][0]["reason"], "Stock received")
        self.assertEqual(received["transactions"][0]["reference_type"], "browser_receive")
        self.assertEqual(received["transactions"][0]["unit_cost"], "0.20")
        self.assertEqual(material_repository.get_material(material_id).last_restocked, date.today())

        status, consumed = self.application.dispatch(
            "POST",
            f"/api/materials/{material_id}/adjust",
            {"expected_revision": received["revision"], "values": {"action": "consume", "quantity": 3, "notes": "Packing orders"}},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(consumed["quantity_on_hand"], 7)
        self.assertEqual(consumed["transactions"][0]["quantity_delta"], -3)

        status, counted = self.application.dispatch(
            "POST",
            f"/api/materials/{material_id}/adjust",
            {"expected_revision": consumed["revision"], "values": {"action": "count", "quantity": 2.5, "notes": "Quarterly count"}},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(counted["quantity_on_hand"], 2.5)
        self.assertEqual(counted["transactions"][0]["reason"], "Stock count correction")

        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch(
                "POST",
                f"/api/materials/{material_id}/adjust",
                {"expected_revision": original_revision, "values": {"action": "receive", "quantity": 1}},
            )
        self.assertEqual(stale.exception.code, "record_conflict")

        with self.assertRaises(BridgeError) as negative:
            self.application.dispatch(
                "POST",
                f"/api/materials/{material_id}/adjust",
                {"expected_revision": counted["revision"], "values": {"action": "consume", "quantity": 3}},
            )
        self.assertEqual(negative.exception.fields["quantity"], "exceeds_on_hand")

    def test_finance_workspace_summarizes_expenses_and_recurring_obligations(self) -> None:
        vendor_id = vendor_repository.save_vendor(Vendor(id=None, name="Studio Utilities"))
        expense_repository.save_expense(
            Expense(
                id=None,
                category="Operations",
                amount=125.50,
                expense_date=date.today(),
                description="Monthly workspace utilities",
                payment_method="Business card",
                vendor_id=vendor_id,
                tags=["studio"],
            )
        )
        expense_repository.save_recurring_expense(
            RecurringExpense(
                id=None,
                category="Software",
                amount=40,
                frequency="Monthly",
                start_date=date.today(),
                next_occurrence=date.today() + timedelta(days=10),
                vendor_id=vendor_id,
                auto_record=True,
            )
        )
        loss_repository.create_loss(
            LossRecord(
                id=None,
                amount=15.25,
                loss_date=date.today(),
                category="Damaged stock",
                description="Damaged during packing",
                details="Set aside for disposal",
                quantity=1,
                unit="item",
                product_id=self.product.id,
                order_id=self.order_id,
                recorded_by="Test Owner",
            )
        )

        status, finance = self.application.dispatch("GET", "/api/finance?limit=50")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(finance["metrics"]["year_to_date_expenses"], "125.50")
        self.assertEqual(finance["metrics"]["month_expenses"], "125.50")
        self.assertEqual(finance["metrics"]["recurring_monthly_estimate"], "40.00")
        self.assertEqual(finance["metrics"]["upcoming_30_days"], "40.00")
        self.assertEqual(finance["metrics"]["year_to_date_losses"], "15.25")
        self.assertEqual(finance["metrics"]["month_losses"], "15.25")
        self.assertEqual(finance["expenses"][0]["vendor"]["name"], "Studio Utilities")
        self.assertEqual(finance["categories"][0]["name"], "Operations")
        self.assertEqual(finance["losses"][0]["product_name"], "Test Product")
        self.assertEqual(finance["losses"][0]["order_id"], self.order_id)
        self.assertEqual(finance["loss_categories"][0]["name"], "Damaged stock")

    def test_reports_workspace_combines_sales_costs_and_overhead(self) -> None:
        expense_repository.save_expense(
            Expense(id=None, category="Operations", amount=10, expense_date=date.today())
        )
        loss_repository.create_loss(
            LossRecord(
                id=None,
                amount=2,
                loss_date=date.today(),
                category="Damaged material",
                description="Test loss",
            )
        )

        status, reports = self.application.dispatch("GET", "/api/reports?period=this_year")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(reports["metrics"]["revenue"], "25.00")
        self.assertEqual(reports["metrics"]["gross_profit"], "17.00")
        self.assertEqual(reports["metrics"]["net_after_overhead"], "5.00")
        self.assertEqual(reports["products"][0]["quantity"], 2)
        self.assertEqual(reports["customers"][0]["name"], "Test Customer")
        self.assertEqual(reports["fulfillment"][0]["status"], "Received")

    def test_browser_report_exports_cover_csv_tax_and_printable_pdf(self) -> None:
        csv_status, orders_csv = self.application.dispatch(
            "GET", "/api/reports/export?kind=orders_csv&period=this_year"
        )
        self.assertEqual(csv_status, HTTPStatus.OK)
        self.assertIsInstance(orders_csv, BinaryDownload)
        self.assertEqual(orders_csv.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"Order Number,Customer", orders_csv.content)
        self.assertIn(b"HN-TEST-001", orders_csv.content)

        tax_status, tax_csv = self.application.dispatch(
            "GET", "/api/reports/export?kind=tax_csv&period=this_year"
        )
        self.assertEqual(tax_status, HTTPStatus.OK)
        self.assertIsInstance(tax_csv, BinaryDownload)
        self.assertIn(b"Taxable Sales,25.00", tax_csv.content)

        order_service.ensure_invoice_runtime()
        pdf_status, sales_pdf = self.application.dispatch(
            "GET", "/api/reports/export?kind=sales_pdf&period=this_year"
        )
        self.assertEqual(pdf_status, HTTPStatus.OK)
        self.assertIsInstance(sales_pdf, BinaryDownload)
        self.assertEqual(sales_pdf.content_type, "application/pdf")
        self.assertTrue(sales_pdf.content.startswith(b"%PDF"))
        self.assertGreater(len(sales_pdf.content), 1000)

    def test_browser_report_export_rejects_unknown_kind(self) -> None:
        with self.assertRaises(BridgeError) as error:
            self.application.dispatch("GET", "/api/reports/export?kind=spreadsheet")
        self.assertEqual(error.exception.status, HTTPStatus.BAD_REQUEST)

    def test_browser_about_exposes_local_runtime_and_release_links(self) -> None:
        status, about = self.application.dispatch("GET", "/api/about")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(about["app_name"], "HustleNest")
        self.assertEqual(about["runtime"], "Local Python backend + browser UI")
        self.assertTrue(about["app_version"].startswith("v"))
        self.assertTrue(about["repository_url"].endswith("RF-YVY/HustleNest"))

    def test_browser_geography_groups_destinations_and_preserves_order_links(self) -> None:
        texas_order_id = order_repository.insert_order(
            Order(
                order_number="HN-TX-001",
                customer_name="Texas Customer",
                customer_address="200 Congress Avenue\nAustin, TX 78701",
                order_date=date.today(),
                status="Processing",
                items=[OrderItem(product_name="Test Product", product_description="Fixture item", product_sku="TEST-001", product_id=self.product.id, quantity=1, unit_price=12.5)],
            )
        )
        settings_repository.set_setting("dashboard_home_city", "Austin")
        settings_repository.set_setting("dashboard_home_state", "TX")

        status, geography = self.application.dispatch("GET", "/api/geography")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(geography["metrics"]["mapped_orders"], 2)
        self.assertEqual(geography["metrics"]["destinations"], 2)
        self.assertEqual(geography["metrics"]["states"], 2)
        self.assertEqual({item["code"] for item in geography["states"]}, {"MO", "TX"})
        self.assertEqual(geography["home"], {"city": "Austin", "state": "TX", "configured": True})
        austin = next(item for item in geography["destinations"] if item["city"] == "Austin")
        self.assertEqual(austin["state_name"], "Texas")
        self.assertEqual(austin["orders"][0]["id"], texas_order_id)
        self.assertEqual(austin["orders"][0]["number"], "HN-TX-001")

    def test_home_workspace_prioritizes_orders_stock_followups_and_goals(self) -> None:
        material_repository.save_material(
            Material(
                id=None,
                sku="HOME-MAT",
                name="Packing paper",
                quantity_on_hand=1,
                reorder_point=5,
                unit_of_measure="rolls",
                cost_per_unit=3,
            )
        )
        crm_repository.save_contact(
            CRMContact(
                id=None,
                customer_name="Follow Up Customer",
                next_follow_up=date.today(),
            )
        )
        goal_repository.save_goal(
            BusinessGoal(
                id=None,
                name="Annual sales",
                metric_type="revenue",
                target_value=100,
                start_date=date.today().replace(month=1, day=1),
                end_date=date.today(),
            )
        )

        status, home = self.application.dispatch("GET", "/api/home")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(home["metrics"]["revenue_ytd"], "25.00")
        self.assertEqual(home["metrics"]["open_orders"], 1)
        self.assertEqual(home["goals"][0]["progress_percent"], 25.0)
        priority_kinds = {item["kind"] for item in home["priorities"]}
        self.assertIn("order", priority_kinds)
        self.assertIn("material", priority_kinds)
        self.assertIn("customer", priority_kinds)

    def test_browser_manages_goals_and_progress_checkpoints(self) -> None:
        status, created = self.application.dispatch(
            "POST",
            "/api/goals",
            {
                "values": {
                    "name": "Quarterly orders",
                    "metric_type": "orders",
                    "target_value": 8,
                    "start_date": date.today().replace(day=1).isoformat(),
                    "end_date": (date.today() + timedelta(days=60)).isoformat(),
                    "owner": "Owner",
                    "progress_notes": "Grow repeat business",
                    "threshold_warning": 0.5,
                    "threshold_critical": 0.25,
                    "auto_calculate": True,
                }
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(created["display_current"], "1.0")
        self.assertEqual(created["progress_percent"], 12.5)

        status, checkpointed = self.application.dispatch(
            "POST",
            f"/api/goals/{created['id']}/checkpoints",
            {
                "expected_revision": created["revision"],
                "values": {
                    "checkpoint_date": date.today().isoformat(),
                    "actual_value": 1,
                    "forecast_value": 7,
                    "notes": "First review",
                },
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(checkpointed["checkpoints"][0]["notes"], "First review")
        self.assertEqual(len(goal_repository.list_checkpoints(created["id"])), 1)

        with self.assertRaisesRegex(BridgeError, "another window"):
            self.application.dispatch(
                "PUT",
                f"/api/goals/{created['id']}",
                {"expected_revision": created["revision"], "values": {"name": "Stale"}},
            )

        status, goals = self.application.dispatch("GET", "/api/goals")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(goals["goals"][0]["name"], "Quarterly orders")
        self.assertIn("crm-followups", goals["metric_options"])

        status, deleted = self.application.dispatch(
            "DELETE",
            f"/api/goals/{created['id']}",
            {"expected_revision": checkpointed["revision"]},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(deleted["deleted"])
        self.assertIsNone(goal_repository.get_goal(created["id"]))

    def test_documents_workspace_reports_file_health_and_linked_record_context(self) -> None:
        invoice_path = Path(self.storage.name) / "invoice-HN-TEST-001.pdf"
        invoice_path.write_bytes(b"%PDF test")
        document_repository.save_document(
            DocumentRecord(
                id=None,
                entity_type="order",
                entity_id=self.order_id,
                file_path=str(invoice_path),
                category="Invoice",
                description="Customer invoice",
                tags=["paid", "2026"],
                stored_at="local",
            )
        )
        document_repository.save_document(
            DocumentRecord(
                id=None,
                entity_type="general",
                entity_id=None,
                file_path=str(Path(self.storage.name) / "missing.txt"),
                category="Notes",
            )
        )

        status, documents = self.application.dispatch("GET", "/api/documents")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(documents["metrics"]["total"], 2)
        self.assertEqual(documents["metrics"]["linked"], 1)
        self.assertEqual(documents["metrics"]["missing"], 1)
        invoice = next(item for item in documents["documents"] if item["category"] == "Invoice")
        self.assertTrue(invoice["exists"])
        self.assertEqual(invoice["entity"]["label"], "HN-TEST-001")
        self.assertEqual(invoice["entity"]["target_view"], "orders")
        self.assertFalse(invoice["managed"])
        with self.assertRaisesRegex(BridgeError, "Only files uploaded"):
            self.application.dispatch(
                "DELETE",
                f"/api/documents/{invoice['id']}",
                {"expected_revision": invoice["revision"], "delete_file": True},
            )
        self.assertTrue(invoice_path.exists())
        self.assertIsNotNone(document_repository.get_document(invoice["id"]))

    def test_browser_uploads_edits_downloads_and_removes_managed_documents(self) -> None:
        content = b"HustleNest managed document"
        status, uploaded = self.application.dispatch(
            "POST",
            "/api/documents",
            {
                "values": {
                    "entity_type": "order",
                    "entity_id": self.order_id,
                    "category": "Reference",
                    "description": "Original notes",
                    "tags": ["customer", "approved", "approved"],
                },
                "file": {
                    "name": "customer notes.txt",
                    "content_base64": base64.b64encode(content).decode("ascii"),
                },
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertTrue(uploaded["managed"])
        self.assertTrue(uploaded["exists"])
        self.assertEqual(uploaded["tags"], ["customer", "approved"])
        managed_path = Path(uploaded["path"])
        self.assertEqual(managed_path.read_bytes(), content)
        self.assertIn("documents", managed_path.parts)

        status, download = self.application.dispatch("GET", f"/api/documents/{uploaded['id']}/download")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIsInstance(download, BinaryDownload)
        self.assertEqual(download.content, content)
        self.assertEqual(download.content_type, "text/plain")

        status, updated = self.application.dispatch(
            "PUT",
            f"/api/documents/{uploaded['id']}",
            {
                "expected_revision": uploaded["revision"],
                "values": {
                    "entity_type": "general",
                    "entity_id": "",
                    "category": "Internal",
                    "description": "Revised notes",
                    "tags": "reviewed, internal",
                },
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["category"], "Internal")
        self.assertEqual(updated["entity"]["type"], "general")

        with self.assertRaisesRegex(BridgeError, "another window"):
            self.application.dispatch(
                "DELETE",
                f"/api/documents/{uploaded['id']}",
                {"expected_revision": uploaded["revision"], "delete_file": True},
            )

        status, deleted = self.application.dispatch(
            "DELETE",
            f"/api/documents/{uploaded['id']}",
            {"expected_revision": updated["revision"], "delete_file": True},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(deleted["file_deleted"])
        self.assertFalse(managed_path.exists())
        self.assertIsNone(document_repository.get_document(uploaded["id"]))

    def test_settings_workspace_excludes_sensitive_configuration_values(self) -> None:
        settings_repository.set_setting("business_name", "Test Studio")
        settings_repository.set_setting("tax_rate_percent", "7.25")
        settings_repository.set_setting("payment_options", '[{"label":"ACH","value":"secret-routing"}]')
        settings_repository.set_setting("cloud_sync_enabled", "1")
        settings_repository.set_setting("cloud_sync_provider", "sftp")
        settings_repository.set_setting("cloud_sync_settings_json", '{"token":"super-secret","folder":"private-folder"}')

        status, settings = self.application.dispatch("GET", "/api/settings")

        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(settings["business"]["name"], "Test Studio")
        self.assertEqual(settings["tax"]["rate_percent"], "7.25")
        self.assertEqual(settings["payments"]["methods"], [{"source_index": 0, "label": "ACH", "configured": True}])
        self.assertEqual(settings["sync"]["configured_field_count"], 2)
        self.assertTrue(settings["summary"]["sensitive_values_excluded"])
        self.assertNotIn("secret-routing", str(settings))
        self.assertNotIn("super-secret", str(settings))
        self.assertNotIn("private-folder", str(settings))

    def test_browser_settings_are_editable_revision_checked_and_persisted(self) -> None:
        _, initial = self.application.dispatch("GET", "/api/settings")
        revision = initial["summary"]["revision"]

        status, updated = self.application.dispatch(
            "PUT",
            "/api/settings",
            {
                "section": "business",
                "expected_revision": revision,
                "values": {
                    "name": "Browser Managed Studio",
                    "home_city": "Tupelo",
                    "home_state": "MS",
                    "show_name_on_dashboard": True,
                },
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["business"]["name"], "Browser Managed Studio")
        self.assertEqual(settings_repository.get_setting("dashboard_home_state"), "MS")
        self.assertNotEqual(updated["summary"]["revision"], revision)

        with self.assertRaises(BridgeError) as conflict:
            self.application.dispatch(
                "PUT",
                "/api/settings",
                {"section": "tax", "expected_revision": revision, "values": {"rate_percent": 5, "show_on_invoice": True, "add_to_total": True}},
            )
        self.assertEqual(conflict.exception.code, "settings_conflict")

        status, browser_updated = self.application.dispatch(
            "PUT",
            "/api/settings",
            {"section": "browser", "expected_revision": updated["summary"]["revision"], "values": {"launch_mode": "none", "browser_id": "system"}},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(browser_updated["browser"]["launch_mode"], "none")
        self.assertEqual(settings_repository.get_setting("browser_launch_mode"), "none")

    def test_browser_saves_appearance_dashboard_preferences_and_managed_logo(self) -> None:
        external_logo = Path(self.storage.name) / "external-logo.png"
        external_logo.write_bytes(b"\x89PNG\r\n\x1a\nexternal")
        settings_repository.set_setting("dashboard_logo_path", str(external_logo))
        _, initial = self.application.dispatch("GET", "/api/settings")
        self.assertTrue(initial["business"]["logo_available"])
        sections = [{**item, "visible": item["key"] != "notifications", "collapsed": item["key"] == "top_customers"} for item in initial["appearance"]["dashboard_sections"]]
        status, updated = self.application.dispatch(
            "PUT",
            "/api/settings",
            {
                "section": "appearance",
                "expected_revision": initial["summary"]["revision"],
                "values": {"theme": "mission-control", "logo_alignment": "bottom-right", "logo_size": 240, "dashboard_sections": sections},
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["appearance"]["theme"], "mission-control")
        self.assertEqual(updated["appearance"]["logo_alignment"], "bottom-right")
        self.assertFalse(next(item for item in updated["appearance"]["dashboard_sections"] if item["key"] == "notifications")["visible"])

        image = b"\x89PNG\r\n\x1a\nmanaged-brand-logo"
        logo_status, branded = self.application.dispatch(
            "POST",
            "/api/settings/logo",
            {"expected_revision": updated["summary"]["revision"], "file": {"name": "brand.jpg", "content_base64": base64.b64encode(image).decode("ascii")}},
        )
        self.assertEqual(logo_status, HTTPStatus.OK)
        self.assertTrue(branded["business"]["logo_available"])
        self.assertTrue(external_logo.exists())
        saved_path = settings_repository.get_app_settings().dashboard_logo_path
        self.assertFalse(Path(saved_path).is_absolute())
        download_status, download = self.application.dispatch("GET", "/api/settings/logo")
        self.assertEqual(download_status, HTTPStatus.OK)
        self.assertEqual(download.content, image)

        delete_status, cleared = self.application.dispatch("DELETE", "/api/settings/logo", {"expected_revision": branded["summary"]["revision"]})
        self.assertEqual(delete_status, HTTPStatus.OK)
        self.assertFalse(cleared["business"]["logo_configured"])
        self.assertFalse((Path(self.storage.name) / "HustleNest" / saved_path).exists())

    def test_browser_saves_owner_profile_and_managed_avatar(self) -> None:
        _, initial = self.application.dispatch("GET", "/api/settings")
        self.assertEqual(initial["profile"]["display_name"], "River Young")
        self.assertEqual(initial["profile"]["initials"], "RY")

        status, updated = self.application.dispatch(
            "PUT",
            "/api/settings",
            {
                "section": "profile",
                "expected_revision": initial["summary"]["revision"],
                "values": {"display_name": "Jordan Avery", "role": "Studio Owner", "email": "jordan@example.com"},
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["profile"]["display_name"], "Jordan Avery")
        self.assertEqual(updated["profile"]["role"], "Studio Owner")
        self.assertEqual(updated["profile"]["email"], "jordan@example.com")
        self.assertEqual(updated["profile"]["initials"], "JA")

        image = b"\x89PNG\r\n\x1a\nmanaged-profile-avatar"
        avatar_status, pictured = self.application.dispatch(
            "POST",
            "/api/settings/profile/avatar",
            {"expected_revision": updated["summary"]["revision"], "file": {"name": "owner.png", "content_base64": base64.b64encode(image).decode("ascii")}},
        )
        self.assertEqual(avatar_status, HTTPStatus.OK)
        self.assertTrue(pictured["profile"]["avatar_available"])
        saved_path = settings_repository.get_setting("profile_avatar_path")
        self.assertFalse(Path(saved_path).is_absolute())
        download_status, download = self.application.dispatch("GET", "/api/settings/profile/avatar")
        self.assertEqual(download_status, HTTPStatus.OK)
        self.assertEqual(download.content, image)

        delete_status, cleared = self.application.dispatch(
            "DELETE",
            "/api/settings/profile/avatar",
            {"expected_revision": pictured["summary"]["revision"]},
        )
        self.assertEqual(delete_status, HTTPStatus.OK)
        self.assertFalse(cleared["profile"]["avatar_configured"])
        self.assertFalse((Path(self.storage.name) / "HustleNest" / saved_path).exists())

    def test_browser_maps_retired_terminal_theme_to_glass(self) -> None:
        settings_repository.set_setting("app_theme", "terminal-green")
        status, settings = self.application.dispatch("GET", "/api/settings")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(settings["appearance"]["theme"], "glass")

    def test_browser_updates_masked_payment_methods_without_exposing_values(self) -> None:
        settings_repository.set_settings({
            "payment_options": '[{"label":"ACH","value":"secret-routing"}]',
            "payment_other": "Mail checks to private box",
        })
        _, initial = self.application.dispatch("GET", "/api/settings")
        self.assertEqual(initial["payments"]["methods"], [{"source_index": 0, "label": "ACH", "configured": True}])
        self.assertTrue(initial["payments"]["other_configured"])
        self.assertNotIn("secret-routing", str(initial))
        self.assertNotIn("private box", str(initial))

        status, updated = self.application.dispatch(
            "PUT",
            "/api/settings",
            {
                "section": "payments",
                "expected_revision": initial["summary"]["revision"],
                "values": {
                    "methods": [
                        {"source_index": 0, "label": "Bank transfer", "replacement": ""},
                        {"source_index": None, "label": "PayPal", "replacement": "billing@example.com"},
                    ],
                    "other_action": "replace",
                    "other_replacement": "Checks payable to Browser Studio",
                },
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        saved = settings_repository.get_app_settings()
        self.assertEqual([(item.label, item.value) for item in saved.payment_options], [("Bank transfer", "secret-routing"), ("PayPal", "billing@example.com")])
        self.assertEqual(saved.payment_other, "Checks payable to Browser Studio")
        self.assertEqual(updated["summary"]["payment_method_count"], 3)
        self.assertNotIn("secret-routing", str(updated))
        self.assertNotIn("billing@example.com", str(updated))

        revision = updated["summary"]["revision"]
        settings_repository.set_setting("payment_options", '[{"label":"Bank transfer","value":"changed-secret"},{"label":"PayPal","value":"billing@example.com"}]')
        _, externally_changed = self.application.dispatch("GET", "/api/settings")
        self.assertNotEqual(externally_changed["summary"]["revision"], revision)
        with self.assertRaises(BridgeError) as conflict:
            self.application.dispatch("PUT", "/api/settings", {"section": "payments", "expected_revision": revision, "values": {"methods": []}})
        self.assertEqual(conflict.exception.code, "settings_conflict")

    def test_browser_updates_masked_cloud_provider_fields(self) -> None:
        _, initial = self.application.dispatch("GET", "/api/sync-settings")
        status, saved = self.application.dispatch(
            "PUT",
            "/api/sync-settings",
            {
                "expected_revision": initial["revision"],
                "enabled": True,
                "provider": "dropbox",
                "interval_minutes": 15,
                "fields": [
                    {"key": "access_token", "action": "replace", "replacement": "super-secret-token"},
                    {"key": "remote_path", "action": "replace", "replacement": "/Apps/HustleNest/private.db"},
                ],
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(saved["ready"])
        self.assertNotIn("super-secret-token", str(saved))
        self.assertNotIn("private.db", str(saved))
        config = settings_repository.get_app_settings().cloud_sync_config
        self.assertEqual(config["access_token"], "super-secret-token")

        token_field = next(field for provider in saved["providers"] if provider["key"] == "dropbox" for field in provider["fields"] if field["key"] == "access_token")
        self.assertTrue(token_field["configured"])
        _, revised = self.application.dispatch(
            "PUT",
            "/api/sync-settings",
            {
                "expected_revision": saved["revision"],
                "enabled": True,
                "provider": "dropbox",
                "interval_minutes": 30,
                "fields": [
                    {"key": "access_token", "action": "keep", "replacement": ""},
                    {"key": "remote_path", "action": "replace", "replacement": "/Apps/HustleNest/revised.db"},
                ],
            },
        )
        self.assertEqual(settings_repository.get_app_settings().cloud_sync_config["access_token"], "super-secret-token")
        self.assertNotEqual(revised["revision"], saved["revision"])

    def test_browser_uploads_snapshot_and_guardedly_pulls_valid_cloud_database(self) -> None:
        remote_folder = Path(self.storage.name) / "sync-target"
        _, initial = self.application.dispatch("GET", "/api/sync-settings")
        _, configured = self.application.dispatch(
            "PUT",
            "/api/sync-settings",
            {
                "expected_revision": initial["revision"], "enabled": True, "provider": "local-folder", "interval_minutes": 5,
                "fields": [
                    {"key": "directory", "action": "replace", "replacement": str(remote_folder)},
                    {"key": "file_name", "action": "replace", "replacement": "shared.db"},
                ],
            },
        )
        upload_status, uploaded = self.application.dispatch("POST", "/api/sync-settings/upload", {"expected_revision": configured["revision"]})
        self.assertEqual(upload_status, HTTPStatus.OK)
        self.assertTrue(uploaded["uploaded"])
        remote_database = remote_folder / "shared.db"
        self.assertTrue(remote_database.exists())
        with sqlite3.connect(remote_database) as check:
            self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertGreater(check.execute("SELECT COUNT(*) FROM products").fetchone()[0], 0)

        settings_repository.set_setting("business_name", "Changed after cloud upload")
        _, current = self.application.dispatch("GET", "/api/sync-settings")
        with self.assertRaises(BridgeError) as unconfirmed:
            self.application.dispatch("POST", "/api/sync-settings/pull", {"expected_revision": current["revision"], "confirmation": "PULL"})
        self.assertEqual(unconfirmed.exception.code, "confirmation_required")
        future = datetime.now().timestamp() + 120
        os.utime(remote_database, (future, future))
        pull_status, pulled = self.application.dispatch("POST", "/api/sync-settings/pull", {"expected_revision": current["revision"], "confirmation": "PULL CLOUD DATA"})
        self.assertEqual(pull_status, HTTPStatus.OK)
        self.assertTrue(pulled["downloaded"])
        self.assertTrue(pulled["restart_required"])
        self.assertNotEqual(settings_repository.get_setting("business_name"), "Changed after cloud upload")
        self.assertTrue(list((Path(self.storage.name) / "HustleNest" / "backups").glob("hustlenest_backup_*.db")))

    def test_browser_rejects_invalid_cloud_database_without_replacing_local_data(self) -> None:
        remote_folder = Path(self.storage.name) / "invalid-sync-target"
        remote_folder.mkdir()
        remote_database = remote_folder / "shared.db"
        remote_database.write_bytes(b"not a sqlite database")
        _, initial = self.application.dispatch("GET", "/api/sync-settings")
        _, configured = self.application.dispatch(
            "PUT", "/api/sync-settings",
            {"expected_revision": initial["revision"], "enabled": True, "provider": "local-folder", "interval_minutes": 5, "fields": [{"key": "directory", "action": "replace", "replacement": str(remote_folder)}, {"key": "file_name", "action": "replace", "replacement": "shared.db"}]},
        )
        future = datetime.now().timestamp() + 120
        os.utime(remote_database, (future, future))
        original_name = settings_repository.get_setting("business_name")
        with self.assertRaises(BridgeError) as invalid:
            self.application.dispatch("POST", "/api/sync-settings/pull", {"expected_revision": configured["revision"], "confirmation": "PULL CLOUD DATA"})
        self.assertEqual(invalid.exception.code, "sync_failed")
        self.assertNotIn(str(remote_folder), invalid.exception.message)
        self.assertEqual(settings_repository.get_setting("business_name"), original_name)
        with sqlite3.connect(Path(self.storage.name) / "HustleNest" / "hustlenest.db") as check:
            self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_browser_creates_downloads_and_guardedly_restores_backups(self) -> None:
        _, initial = self.application.dispatch("GET", "/api/backups")
        settings_status, configured = self.application.dispatch(
            "PUT",
            "/api/backups",
            {
                "expected_revision": initial["revision"],
                "values": {"enabled": True, "using_managed_folder": True, "folder": "", "frequency": "manual", "max_backups": 3},
            },
        )
        self.assertEqual(settings_status, HTTPStatus.OK)
        self.assertTrue(configured["settings"]["using_managed_folder"])

        backup_status, created = self.application.dispatch("POST", "/api/backups", {"expected_revision": configured["revision"]})
        self.assertEqual(backup_status, HTTPStatus.CREATED)
        self.assertEqual(created["summary"]["count"], 1)
        backup = created["backups"][0]
        download_status, download = self.application.dispatch("GET", f"/api/backups/{backup['id']}/download")
        self.assertEqual(download_status, HTTPStatus.OK)
        self.assertIsInstance(download, BinaryDownload)
        self.assertGreater(len(download.content), 0)
        download_path = Path(self.storage.name) / "download-check.db"
        download_path.write_bytes(download.content)
        with sqlite3.connect(download_path) as check:
            self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")

        settings_repository.set_setting("business_name", "Changed after backup")
        with self.assertRaises(BridgeError) as confirmation:
            self.application.dispatch(
                "POST", f"/api/backups/{backup['id']}/restore", {"expected_revision": created["revision"], "confirmation": "RESTORE"}
            )
        self.assertEqual(confirmation.exception.code, "confirmation_required")

        restore_status, restored = self.application.dispatch(
            "POST",
            f"/api/backups/{backup['id']}/restore",
            {"expected_revision": created["revision"], "confirmation": f"RESTORE {backup['filename']}"},
        )
        self.assertEqual(restore_status, HTTPStatus.OK)
        self.assertTrue(restored["restart_required"])
        self.assertNotEqual(settings_repository.get_setting("business_name"), "Changed after backup")

    def test_browser_previews_maps_and_imports_products_orders_and_customers(self) -> None:
        def upload(name: str, content: str) -> dict[str, str]:
            return {"name": name, "content_base64": base64.b64encode(content.encode("utf-8")).decode("ascii")}

        self.product.description = "Keep this description"
        self.product.photo_path = "media/products/existing.png"
        self.product.pricing_components = [CostComponent("Packaging", 1.25)]
        product_repository.update_product(self.product)
        product_file = upload(
            "products.csv",
            "SKU,Product Name,Inventory Count,Default Price\nTEST-001,Updated Product,17,$19.50\nNEW-002,New Product,4,8.25\n",
        )
        preview_status, preview = self.application.dispatch(
            "POST", "/api/imports/preview", {"import_type": "products", "file": product_file}
        )
        self.assertEqual(preview_status, HTTPStatus.OK)
        self.assertEqual(preview["columns"][0]["suggested_field"], "sku")
        self.assertEqual(preview["columns"][1]["suggested_field"], "name")
        mappings = [
            {"source_column": column["index"], "target_field": column["suggested_field"]}
            for column in preview["columns"] if column["suggested_field"]
        ]
        import_status, imported = self.application.dispatch(
            "POST", "/api/imports/execute", {"import_type": "products", "file": product_file, "mappings": mappings, "skip_duplicates": False}
        )
        self.assertEqual(import_status, HTTPStatus.OK)
        self.assertEqual(imported["imported_count"], 2)
        updated_product = product_repository.get_product_by_sku("TEST-001")
        self.assertEqual(updated_product.name, "Updated Product")
        self.assertEqual(updated_product.inventory_count, 17)
        self.assertEqual(updated_product.default_unit_price, 19.5)
        self.assertEqual(updated_product.description, "Keep this description")
        self.assertEqual(updated_product.photo_path, "media/products/existing.png")
        self.assertEqual(updated_product.pricing_components[0].label, "Packaging")
        self.assertEqual(product_repository.get_product_by_sku("NEW-002").inventory_count, 4)

        order_file = upload(
            "orders.csv",
            "Order Number,Customer Name,Order Date,Status,Notes\nHN-TEST-001,Test Customer,07/16/2026,Processing,Imported update\n",
        )
        _, order_preview = self.application.dispatch("POST", "/api/imports/preview", {"import_type": "orders", "file": order_file})
        order_mappings = [{"source_column": item["index"], "target_field": item["suggested_field"]} for item in order_preview["columns"] if item["suggested_field"]]
        _, order_result = self.application.dispatch("POST", "/api/imports/execute", {"import_type": "orders", "file": order_file, "mappings": order_mappings, "skip_duplicates": False})
        self.assertEqual(order_result["imported_count"], 1)
        updated_order = order_repository.fetch_order(self.order_id)
        self.assertEqual(updated_order.status, "Processing")
        self.assertEqual(updated_order.notes, "Imported update")
        self.assertEqual(len(updated_order.items), 1)

        customer_file = upload("customers.csv", "Customer Name,Email,Phone,Tags\nKlay Cox,klay@example.com,555-0199,VIP;Referral\n")
        _, customer_preview = self.application.dispatch("POST", "/api/imports/preview", {"import_type": "customers", "file": customer_file})
        customer_mappings = [{"source_column": item["index"], "target_field": item["suggested_field"]} for item in customer_preview["columns"] if item["suggested_field"]]
        _, customer_result = self.application.dispatch("POST", "/api/imports/execute", {"import_type": "customers", "file": customer_file, "mappings": customer_mappings, "skip_duplicates": True})
        self.assertEqual(customer_result["imported_count"], 1)
        klay = next(contact for contact in crm_repository.list_contacts() if contact.customer_name == "Klay Cox")
        self.assertEqual(klay.tags, ["VIP", "Referral"])

        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["SKU", "Product Name", "Inventory Count"])
        sheet.append(["XLSX-001", "Excel Product", 6])
        excel_bytes = io.BytesIO()
        workbook.save(excel_bytes)
        workbook.close()
        excel_file = {"name": "products.xlsx", "content_base64": base64.b64encode(excel_bytes.getvalue()).decode("ascii")}
        _, excel_preview = self.application.dispatch("POST", "/api/imports/preview", {"import_type": "products", "file": excel_file})
        excel_mappings = [{"source_column": item["index"], "target_field": item["suggested_field"]} for item in excel_preview["columns"] if item["suggested_field"]]
        _, excel_result = self.application.dispatch("POST", "/api/imports/execute", {"import_type": "products", "file": excel_file, "mappings": excel_mappings})
        self.assertEqual(excel_result["imported_count"], 1)
        self.assertEqual(product_repository.get_product_by_sku("XLSX-001").inventory_count, 6)

        with self.assertRaises(BridgeError) as missing:
            self.application.dispatch("POST", "/api/imports/execute", {"import_type": "products", "file": product_file, "mappings": [{"source_column": 0, "target_field": "sku"}]})
        self.assertEqual(missing.exception.code, "validation_failed")

    def test_browser_launcher_honors_system_and_manual_modes(self) -> None:
        settings_repository.set_settings({"browser_launch_mode": "system", "browser_id": "system"})
        with patch("hustlenest.browser_launcher.webbrowser.open", return_value=True) as opener:
            self.assertTrue(browser_launcher.launch_configured_browser("http://localhost:3000"))
            opener.assert_called_once_with("http://localhost:3000", new=2)

        settings_repository.set_setting("browser_launch_mode", "none")
        with patch("hustlenest.browser_launcher.webbrowser.open") as opener:
            self.assertFalse(browser_launcher.launch_configured_browser("http://localhost:3000"))
            opener.assert_not_called()

    def test_quick_add_creates_core_business_records(self) -> None:
        entries = [
            ("customer", {"name": "Quick Customer", "email": "quick@example.com"}),
            ("product", {"sku": "QUICK-001", "name": "Quick Product", "inventory_count": 4, "unit_cost": 3.5, "unit_price": 9}),
            ("vendor", {"name": "Quick Supply", "contact_name": "Alex"}),
        ]
        created: dict[str, int] = {}
        for entry_type, values in entries:
            status, result = self.application.dispatch("POST", "/api/quick-add", {"type": entry_type, "values": values})
            self.assertEqual(status, HTTPStatus.CREATED)
            created[entry_type] = result["id"]

        material_values = {"sku": "MAT-QUICK", "name": "Quick Material", "quantity_on_hand": 12.5, "reorder_point": 3, "cost_per_unit": 1.25, "vendor_id": created["vendor"]}
        expense_values = {"category": "Supplies", "amount": 24.5, "date": date.today().isoformat(), "vendor_id": created["vendor"]}
        loss_values = {"category": "Damage", "amount": 8, "date": date.today().isoformat(), "description": "Shop damage"}
        for entry_type, values in (("material", material_values), ("expense", expense_values), ("loss", loss_values)):
            status, result = self.application.dispatch("POST", "/api/quick-add", {"type": entry_type, "values": values})
            self.assertEqual(status, HTTPStatus.CREATED)
            self.assertGreater(result["id"], 0)

        self.assertEqual(product_repository.get_product_by_sku("QUICK-001").inventory_count, 4)
        self.assertTrue(any(item.customer_name == "Quick Customer" for item in crm_repository.list_contacts()))
        self.assertTrue(any(item.sku == "MAT-QUICK" for item in material_repository.list_materials()))
        self.assertTrue(any(item.category == "Supplies" for item in expense_repository.list_expenses()))
        self.assertTrue(any(item.category == "Damage" for item in loss_repository.fetch_losses()))

    def test_quick_add_rejects_invalid_and_duplicate_records(self) -> None:
        with self.assertRaises(BridgeError) as invalid:
            self.application.dispatch("POST", "/api/quick-add", {"type": "expense", "values": {"category": "Supplies", "amount": 0, "date": "not-a-date"}})
        self.assertEqual(invalid.exception.code, "validation_failed")
        self.assertEqual(invalid.exception.fields["amount"], "must_be_positive")

        with self.assertRaises(BridgeError) as duplicate:
            self.application.dispatch("POST", "/api/quick-add", {"type": "product", "values": {"sku": "TEST-001", "name": "Duplicate"}})
        self.assertEqual(duplicate.exception.code, "duplicate_sku")

    def test_browser_deletes_operational_records_with_revision_guards(self) -> None:
        created: dict[str, int] = {}
        payloads = {
            "customer": {"name": "Delete Customer"},
            "product": {"sku": "DELETE-001", "name": "Delete Product"},
            "material": {"sku": "DELETE-MAT", "name": "Delete Material"},
            "vendor": {"name": "Delete Vendor"},
            "expense": {"category": "Delete Expense", "amount": 3, "date": date.today().isoformat()},
            "recurring": {"category": "Delete Recurring", "amount": 4, "frequency": "monthly", "start_date": date.today().isoformat(), "next_occurrence": date.today().isoformat()},
            "loss": {"category": "Delete Loss", "amount": 2, "date": date.today().isoformat()},
        }
        for entry_type, values in payloads.items():
            _, result = self.application.dispatch("POST", "/api/quick-add", {"type": entry_type, "values": values})
            created[entry_type] = result["id"]

        _, customers = self.application.dispatch("GET", "/api/customers?query=Delete%20Customer")
        _, products = self.application.dispatch("GET", "/api/products?query=DELETE-001")
        _, materials = self.application.dispatch("GET", "/api/materials?query=DELETE-MAT")
        _, vendors = self.application.dispatch("GET", "/api/vendors?query=Delete%20Vendor")
        _, finance = self.application.dispatch("GET", "/api/finance")
        revisions = {
            "customer": customers[0]["revision"],
            "product": products[0]["revision"],
            "material": materials[0]["revision"],
            "vendor": vendors[0]["revision"],
            "expense": next(item["revision"] for item in finance["expenses"] if item["id"] == created["expense"]),
            "recurring": next(item["revision"] for item in finance["recurring"] if item["id"] == created["recurring"]),
            "loss": next(item["revision"] for item in finance["losses"] if item["id"] == created["loss"]),
        }

        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch("DELETE", f"/api/records/customer/{created['customer']}", {"expected_revision": "stale"})
        self.assertEqual(stale.exception.code, "record_conflict")

        for entry_type, record_id in created.items():
            status, result = self.application.dispatch("DELETE", f"/api/records/{entry_type}/{record_id}", {"expected_revision": revisions[entry_type]})
            self.assertEqual(status, HTTPStatus.OK)
            self.assertEqual(result["id"], record_id)

        self.assertIsNone(crm_repository.get_contact(created["customer"]))
        self.assertIsNone(material_repository.get_material(created["material"]))
        self.assertIsNone(vendor_repository.get_vendor(created["vendor"]))
        self.assertIsNone(expense_repository.get_expense(created["expense"]))
        self.assertIsNone(expense_repository.get_recurring_expense(created["recurring"]))
        self.assertIsNone(loss_repository.get_loss(created["loss"]))
        _, trash = self.application.dispatch("GET", "/api/trash")
        self.assertTrue(any(item["id"] == created["product"] for item in trash["items"] if item["type"] == "product"))

    def test_browser_deletes_customer_interaction_with_revision_guard(self) -> None:
        customer = next(item for item in crm_repository.list_contacts() if item.customer_name == "Test Customer")
        _, detail = self.application.dispatch("GET", f"/api/customers/{customer.id}")
        _, updated = self.application.dispatch(
            "POST",
            f"/api/customers/{customer.id}/interactions",
            {"expected_revision": detail["revision"], "values": {"interaction_date": date.today().isoformat(), "summary": "Temporary note"}},
        )
        interaction = updated["interactions"][0]
        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch("DELETE", f"/api/customers/{customer.id}/interactions/{interaction['id']}", {"expected_revision": "stale"})
        self.assertEqual(stale.exception.code, "record_conflict")
        status, refreshed = self.application.dispatch(
            "DELETE",
            f"/api/customers/{customer.id}/interactions/{interaction['id']}",
            {"expected_revision": interaction["revision"]},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(refreshed["interactions"], [])

    def test_browser_promotes_order_only_customer_to_contact(self) -> None:
        order_repository.insert_order(
            Order(
                order_number="HN-PROMOTE-001",
                customer_name="Klay Cox",
                customer_address="12 Example Road\nTulsa, OK 74103",
                order_date=date.today(),
                status="Received",
                items=[OrderItem(product_name="Test Product", product_description="Fixture item", product_sku="TEST-001", product_id=self.product.id, quantity=1, unit_price=12.5)],
            )
        )
        _, before = self.application.dispatch("GET", "/api/customers?query=Klay%20Cox")
        self.assertEqual(before[0]["name"], "Klay Cox")
        self.assertIsNone(before[0]["id"])

        status, promoted = self.application.dispatch("POST", "/api/customers/promote", {"name": "Klay Cox"})
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertGreater(promoted["id"], 0)
        self.assertIn("Tulsa", promoted["address"])

        _, after = self.application.dispatch("GET", "/api/customers?query=Klay%20Cox")
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["key"], f"crm:{promoted['id']}")

    def test_browser_updates_operational_records_without_losing_hidden_fields(self) -> None:
        customer = next(item for item in crm_repository.list_contacts() if item.customer_name == "Test Customer")
        customer.tags = ["repeat"]
        customer.notes = "Old note"
        crm_repository.save_contact(customer)
        vendor_id = vendor_repository.save_vendor(Vendor(id=None, name="Original Vendor", account_number="ACCT-7", preferred_payment_method="ACH"))
        material_id = material_repository.save_material(Material(id=None, sku="EDIT-MAT", name="Old Material", quantity_on_hand=2, last_restocked=date.today(), lead_time_days=9, vendor_id=vendor_id))
        self.product.pricing_components = [CostComponent("Packaging", 2)]
        product_repository.update_product(self.product)

        updates = [
            ("customer", customer.id, {"name": "Updated Customer", "company": "Studio", "email": "new@example.com", "notes": "New note"}),
            ("product", self.product.id, {"sku": "TEST-EDIT", "name": "Updated Product", "description": "Edited", "inventory_count": 7, "unit_cost": 5, "unit_price": 15}),
            ("material", material_id, {"sku": "EDIT-MAT", "name": "Updated Material", "category": "Wood", "unit_of_measure": "board ft", "quantity_on_hand": 8, "reorder_point": 2, "cost_per_unit": 4, "vendor_id": vendor_id}),
            ("vendor", vendor_id, {"name": "Updated Vendor", "contact_name": "Morgan", "account_number": "ACCT-8", "preferred_payment_method": "Card"}),
        ]
        for entry_type, record_id, values in updates:
            status, result = self.application.dispatch("PUT", f"/api/records/{entry_type}/{record_id}", {"values": values})
            self.assertEqual(status, HTTPStatus.OK)
            self.assertEqual(result["id"], record_id)

        saved_customer = crm_repository.get_contact(customer.id)
        self.assertEqual(saved_customer.customer_name, "Updated Customer")
        self.assertEqual(saved_customer.tags, ["repeat"])
        saved_product = product_repository.get_product_by_id(self.product.id)
        self.assertEqual(saved_product.inventory_count, 7)
        self.assertEqual(saved_product.base_unit_cost, 5)
        self.assertEqual(saved_product.total_unit_cost, 7)
        self.assertEqual(saved_product.pricing_components[0].label, "Packaging")
        saved_material = material_repository.get_material(material_id)
        self.assertEqual(saved_material.name, "Updated Material")
        self.assertEqual(saved_material.last_restocked, date.today())
        self.assertEqual(saved_material.lead_time_days, 9)
        saved_vendor = vendor_repository.get_vendor(vendor_id)
        self.assertEqual(saved_vendor.account_number, "ACCT-8")
        self.assertEqual(saved_vendor.preferred_payment_method, "Card")

        _, customers = self.application.dispatch("GET", "/api/customers?query=Updated%20Customer")
        stale_revision = customers[0]["revision"]
        saved_customer.phone = "555-0199"
        crm_repository.save_contact(saved_customer)
        with self.assertRaises(BridgeError) as conflict:
            self.application.dispatch("PUT", f"/api/records/customer/{customer.id}", {"expected_revision": stale_revision, "values": {"name": "Stale Customer"}})
        self.assertEqual(conflict.exception.code, "record_conflict")

        with self.assertRaises(BridgeError) as missing:
            self.application.dispatch("PUT", "/api/records/product/999999", {"values": {"sku": "MISS", "name": "Missing"}})
        self.assertEqual(missing.exception.code, "product_not_found")

    def test_browser_manages_product_status_costing_and_forecast(self) -> None:
        _, products = self.application.dispatch("GET", "/api/products?limit=200")
        initial = next(item for item in products if item["id"] == self.product.id)
        self.assertIn("average_weekly_sales", initial["forecast"])
        self.assertEqual(initial["cost_components"], [])

        status, result = self.application.dispatch(
            "PUT",
            f"/api/records/product/{self.product.id}",
            {
                "expected_revision": initial["revision"],
                "values": {
                    "sku": self.product.sku,
                    "name": self.product.name,
                    "description": "Costed product",
                    "inventory_count": 10,
                    "unit_cost": 4,
                    "unit_price": 18,
                    "status": "Discontinued",
                    "cost_components": '[{"label":"Packaging","amount":"1.25"},{"label":"Labor","amount":"2.50"}]',
                },
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(result["id"], self.product.id)
        saved = product_repository.get_product_by_id(self.product.id)
        self.assertEqual(saved.status, "Discontinued")
        self.assertEqual(saved.total_unit_cost, 7.75)
        self.assertEqual([item.label for item in saved.pricing_components], ["Packaging", "Labor"])

        _, refreshed = self.application.dispatch("GET", "/api/products?limit=200")
        updated = next(item for item in refreshed if item["id"] == self.product.id)
        self.assertEqual(updated["additional_unit_cost"], "3.75")
        self.assertEqual(updated["unit_cost"], "7.75")
        self.assertEqual(updated["cost_components"][0], {"label": "Packaging", "amount": "1.25"})

        with self.assertRaises(BridgeError) as invalid:
            self.application.dispatch(
                "PUT",
                f"/api/records/product/{self.product.id}",
                {"values": {**{"sku": saved.sku, "name": saved.name, "inventory_count": 10, "unit_cost": 4, "unit_price": 18, "status": "Available"}, "cost_components": '[{"label":"Bad","amount":-1}]'}},
            )
        self.assertEqual(invalid.exception.code, "validation_failed")

    def test_browser_manages_validated_product_photos(self) -> None:
        _, products = self.application.dispatch("GET", "/api/products?limit=200")
        initial = next(item for item in products if item["id"] == self.product.id)
        image = b"\x89PNG\r\n\x1a\n" + b"browser-product-photo"
        status, saved = self.application.dispatch(
            "POST",
            f"/api/products/{self.product.id}/photo",
            {
                "expected_revision": initial["revision"],
                "file": {"name": "unsafe-name.jpg", "content_base64": base64.b64encode(image).decode("ascii")},
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(saved["photo_configured"])
        self.assertTrue(saved["photo_available"])
        product = product_repository.get_product_by_id(self.product.id)
        self.assertTrue(product.photo_path.endswith(".png"))
        self.assertFalse(Path(product.photo_path).is_absolute())

        download_status, download = self.application.dispatch("GET", f"/api/products/{self.product.id}/photo")
        self.assertEqual(download_status, HTTPStatus.OK)
        self.assertIsInstance(download, BinaryDownload)
        self.assertEqual(download.content_type, "image/png")
        self.assertEqual(download.content, image)

        with self.assertRaises(BridgeError) as unsupported:
            self.application.dispatch(
                "POST",
                f"/api/products/{self.product.id}/photo",
                {"expected_revision": saved["revision"], "file": {"name": "bad.exe", "content_base64": base64.b64encode(b"not an image").decode("ascii")}},
            )
        self.assertEqual(unsupported.exception.code, "validation_failed")

        delete_status, cleared = self.application.dispatch(
            "DELETE", f"/api/products/{self.product.id}/photo", {"expected_revision": saved["revision"]}
        )
        self.assertEqual(delete_status, HTTPStatus.OK)
        self.assertFalse(cleared["photo_configured"])
        self.assertFalse(cleared["photo_available"])
        self.assertFalse((Path(self.storage.name) / "HustleNest" / product.photo_path).exists())

    def test_browser_updates_finance_records_and_preserves_links(self) -> None:
        expense_id = expense_repository.save_expense(Expense(id=None, category="Old Expense", amount=10, expense_date=date.today(), tags=["tax"], notes="Before"))
        loss_id = loss_repository.create_loss(LossRecord(id=None, amount=6, loss_date=date.today(), category="Old Loss", description="Before", quantity=2, unit="each", order_id=self.order_id, product_id=self.product.id, recorded_by="Owner"))
        _, finance = self.application.dispatch("GET", "/api/finance")
        expense_revision = next(item["revision"] for item in finance["expenses"] if item["id"] == expense_id)
        loss_revision = next(item["revision"] for item in finance["losses"] if item["id"] == loss_id)

        expense_status, _ = self.application.dispatch("PUT", f"/api/records/expense/{expense_id}", {"expected_revision": expense_revision, "values": {"category": "Travel", "amount": 25.5, "date": date.today().isoformat(), "description": "Mileage", "payment_method": "Card", "notes": "Updated"}})
        loss_status, _ = self.application.dispatch("PUT", f"/api/records/loss/{loss_id}", {"expected_revision": loss_revision, "values": {"category": "Damage", "amount": 8.5, "date": date.today().isoformat(), "description": "Scratched", "notes": "Updated details"}})
        self.assertEqual(expense_status, HTTPStatus.OK)
        self.assertEqual(loss_status, HTTPStatus.OK)

        saved_expense = expense_repository.get_expense(expense_id)
        self.assertEqual(saved_expense.category, "Travel")
        self.assertEqual(saved_expense.tags, ["tax"])
        saved_loss = loss_repository.get_loss(loss_id)
        self.assertEqual(saved_loss.category, "Damage")
        self.assertEqual(saved_loss.order_id, self.order_id)
        self.assertEqual(saved_loss.product_id, self.product.id)
        self.assertEqual(saved_loss.quantity, 2)
        self.assertEqual(saved_loss.recorded_by, "Owner")

        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch("PUT", f"/api/records/loss/{loss_id}", {"expected_revision": loss_revision, "values": {"category": "Stale", "amount": 1, "date": date.today().isoformat()}})
        self.assertEqual(stale.exception.code, "record_conflict")

    def test_browser_creates_and_updates_recurring_expenses_safely(self) -> None:
        start = date.today()
        next_due = start + timedelta(days=7)
        end = start + timedelta(days=90)
        status, created = self.application.dispatch(
            "POST",
            "/api/quick-add",
            {
                "type": "recurring",
                "values": {
                    "category": "Software",
                    "amount": 49,
                    "frequency": "monthly",
                    "start_date": start.isoformat(),
                    "next_occurrence": next_due.isoformat(),
                    "end_date": end.isoformat(),
                    "auto_record": True,
                    "notes": "Created in browser",
                },
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        recurring_id = created["id"]
        saved = expense_repository.get_recurring_expense(recurring_id)
        self.assertEqual(saved.frequency, "Monthly")
        self.assertTrue(saved.auto_record)

        saved.day_of_month = 15
        expense_repository.save_recurring_expense(saved)
        _, finance = self.application.dispatch("GET", "/api/finance")
        revision = next(item["revision"] for item in finance["recurring"] if item["id"] == recurring_id)
        update_values = {
            "category": "Business software",
            "amount": 59,
            "frequency": "quarterly",
            "start_date": start.isoformat(),
            "next_occurrence": next_due.isoformat(),
            "end_date": end.isoformat(),
            "auto_record": False,
            "notes": "Updated in browser",
        }
        update_status, _ = self.application.dispatch(
            "PUT",
            f"/api/records/recurring/{recurring_id}",
            {"expected_revision": revision, "values": update_values},
        )
        self.assertEqual(update_status, HTTPStatus.OK)
        updated = expense_repository.get_recurring_expense(recurring_id)
        self.assertEqual(updated.category, "Business software")
        self.assertEqual(updated.frequency, "Quarterly")
        self.assertEqual(updated.day_of_month, 15)
        self.assertFalse(updated.auto_record)

        with self.assertRaises(BridgeError) as stale:
            self.application.dispatch(
                "PUT",
                f"/api/records/recurring/{recurring_id}",
                {"expected_revision": revision, "values": update_values},
            )
        self.assertEqual(stale.exception.code, "record_conflict")

        with self.assertRaises(BridgeError) as invalid:
            self.application.dispatch(
                "POST",
                "/api/quick-add",
                {
                    "type": "recurring",
                    "values": {
                        "category": "Invalid schedule",
                        "amount": 10,
                        "frequency": "monthly",
                        "start_date": start.isoformat(),
                        "next_occurrence": (start - timedelta(days=1)).isoformat(),
                    },
                },
            )
        self.assertEqual(invalid.exception.code, "validation_failed")
        self.assertEqual(invalid.exception.fields["next_occurrence"], "before_start")

    def test_browser_manages_the_complete_trash_lifecycle(self) -> None:
        _, products = self.application.dispatch("GET", "/api/products")
        product_revision = next(item["revision"] for item in products if item["id"] == self.product.id)

        order_status, trashed_order = self.application.dispatch(
            "DELETE", f"/api/orders/{self.order_id}", {"expected_status": "Received"}
        )
        product_status, trashed_product = self.application.dispatch(
            "DELETE", f"/api/records/product/{self.product.id}", {"expected_revision": product_revision}
        )
        self.assertEqual(order_status, HTTPStatus.OK)
        self.assertEqual(product_status, HTTPStatus.OK)
        self.assertTrue(trashed_order["trashed"])
        self.assertTrue(trashed_product["trashed"])

        _, trash = self.application.dispatch("GET", "/api/trash")
        self.assertEqual(trash["metrics"], {"total": 2, "orders": 1, "products": 1})
        deleted_order = next(item for item in trash["items"] if item["type"] == "order")
        deleted_product = next(item for item in trash["items"] if item["type"] == "product")
        self.assertEqual(deleted_order["name"], "HN-TEST-001")

        restore_status, restored = self.application.dispatch(
            "POST",
            f"/api/trash/order/{self.order_id}/restore",
            {"expected_revision": deleted_order["revision"]},
        )
        self.assertEqual(restore_status, HTTPStatus.OK)
        self.assertEqual(restored["action"], "restore")
        self.assertIsNotNone(order_repository.fetch_order(self.order_id))

        with self.assertRaises(BridgeError) as unconfirmed:
            self.application.dispatch(
                "DELETE",
                f"/api/trash/product/{self.product.id}",
                {"expected_revision": deleted_product["revision"]},
            )
        self.assertEqual(unconfirmed.exception.code, "confirmation_required")

        delete_status, deleted = self.application.dispatch(
            "DELETE",
            f"/api/trash/product/{self.product.id}",
            {"expected_revision": deleted_product["revision"], "confirm": True},
        )
        self.assertEqual(delete_status, HTTPStatus.OK)
        self.assertEqual(deleted["action"], "delete")
        self.assertIsNone(product_repository.get_product_by_id(self.product.id))

        another = product_repository.create_product("TRASH-002", "Second deleted product", mark_complete=True)
        self.assertTrue(soft_delete_service.soft_delete_product(another.id))
        with self.assertRaises(BridgeError) as changed:
            self.application.dispatch("DELETE", "/api/trash", {"confirmation": "EMPTY TRASH", "expected_count": 0})
        self.assertEqual(changed.exception.code, "record_conflict")
        empty_status, result = self.application.dispatch(
            "DELETE", "/api/trash", {"confirmation": "EMPTY TRASH", "expected_count": 1}
        )
        self.assertEqual(empty_status, HTTPStatus.OK)
        self.assertEqual(result["deleted"], 1)


if __name__ == "__main__":
    unittest.main()
