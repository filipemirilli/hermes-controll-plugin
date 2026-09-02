import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controll_plugin_tools", PLUGIN_ROOT / "tools.py")
TOOLS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOLS)


class ControllPluginTests(unittest.TestCase):
    def test_default_endpoint_uses_current_controll_domain(self):
        with patch.dict(TOOLS.os.environ, {}, clear=True):
            self.assertEqual(TOOLS._base_url(), "https://controll.cromoz.com.br")

    def test_create_transaction_builds_supported_payload(self):
        response = {"ok": True, "created": True, "transaction": {"id": 42}}
        with patch.object(TOOLS, "_api_request", return_value=response) as api_request:
            result = json.loads(TOOLS.create_transaction({
                "date": "2026-08-11",
                "description": "Compra no mercado",
                "category": "🛒 Mercado",
                "type": "expense",
                "amount": 35.9,
                "source_person": "Filipe",
                "payment_method": "debit",
                "payment_bank": "Nubank",
            }))

        self.assertTrue(result["ok"])
        method, path, payload = api_request.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/api/integrations/transactions")
        self.assertEqual(payload["amount"], 35.9)
        self.assertEqual(payload["sourcePerson"], "Filipe")
        self.assertEqual(payload["paymentMethod"], "debit")
        self.assertEqual(payload["paymentBank"], "Nubank")
        self.assertFalse(payload["allowDuplicate"])
        self.assertTrue(payload["externalEventId"].startswith("hermes-plugin-"))

    def test_create_transaction_rejects_investment_type(self):
        result = json.loads(TOOLS.create_transaction({
            "date": "2026-08-11",
            "description": "Aplicacao",
            "category": "Investimento",
            "type": "investment",
            "amount": 100,
            "source_person": "Filipe",
        }))
        self.assertFalse(result["ok"])
        self.assertIn("income ou expense", result["error"])

    def test_create_transaction_rejects_non_operational_movement(self):
        result = json.loads(TOOLS.create_transaction({
            "date": "2026-08-11",
            "description": "Pagamento de fatura",
            "category": "Cartao de credito",
            "type": "expense",
            "amount": 100,
            "source_person": "Renata",
        }))
        self.assertFalse(result["ok"])
        self.assertIn("manualmente no Controll", result["error"])

    def test_create_transaction_preserves_possible_duplicate_details(self):
        duplicate = {
            "code": "possible_duplicate",
            "error": "Possivel duplicidade encontrada",
            "duplicate": {"id": 12, "description": "Mercado"},
        }
        with patch.object(
            TOOLS,
            "_api_request",
            side_effect=TOOLS.ControllApiError(duplicate["error"], duplicate),
        ):
            result = json.loads(TOOLS.create_transaction({
                "date": "2026-08-11",
                "description": "Mercado",
                "category": "Mercado",
                "type": "expense",
                "amount": 35.9,
                "source_person": "Filipe",
                "payment_method": "pix",
                "payment_bank": "Nubank",
            }))

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "possible_duplicate")
        self.assertEqual(result["duplicate"]["id"], 12)

    def test_register_credit_card_invoice_creates_current_and_future_installments(self):
        response = {
            "ok": True,
            "created": True,
            "idempotent": False,
            "transaction": {"id": 42},
        }
        with patch.object(TOOLS, "_api_request", return_value=response) as api_request:
            result = json.loads(TOOLS.register_credit_card_invoice({
                "invoice_due_date": "2026-08-10",
                "source_person": "Filipe",
                "payment_bank": "Nubank",
                "items": [{
                    "description": "Notebook (03/10)",
                    "category": "🧥 Compras",
                    "installment_amount": 350,
                    "current_installment": 3,
                    "total_installments": 10,
                }],
            }))

        self.assertTrue(result["ok"])
        self.assertEqual(result["scheduledCount"], 8)
        self.assertEqual(result["createdCount"], 8)
        self.assertEqual(result["alreadyRegisteredCount"], 0)
        payloads = [call.args[2] for call in api_request.call_args_list]
        self.assertEqual(len(payloads), 8)
        self.assertEqual(
            [payload["date"] for payload in payloads],
            [
                "2026-08-10", "2026-09-10", "2026-10-10", "2026-11-10",
                "2026-12-10", "2027-01-10", "2027-02-10", "2027-03-10",
            ],
        )
        self.assertEqual(payloads[0]["description"], "Notebook (3/10)")
        self.assertEqual(payloads[-1]["description"], "Notebook (10/10)")
        self.assertTrue(all(payload["paymentMethod"] == "credit" for payload in payloads))
        self.assertTrue(all(payload["paymentBank"] == "Nubank" for payload in payloads))
        self.assertTrue(all(payload["type"] == "expense" for payload in payloads))
        self.assertEqual(len({payload["externalEventId"] for payload in payloads}), 8)

    def test_next_invoice_reconciles_already_scheduled_installments(self):
        first_invoice = {
            "invoice_due_date": "2026-08-10",
            "source_person": "Filipe",
            "payment_bank": "Nubank",
            "items": [{
                "description": "Notebook 3/10",
                "category": "🧥 Compras",
                "installment_amount": 350,
                "current_installment": 3,
                "total_installments": 10,
            }],
        }
        next_invoice = {
            **first_invoice,
            "invoice_due_date": "2026-09-10",
            "items": [{
                **first_invoice["items"][0],
                "current_installment": 4,
            }],
        }
        with patch.object(
            TOOLS,
            "_api_request",
            return_value={"ok": True, "created": True},
        ) as api_request:
            first_result = json.loads(TOOLS.register_credit_card_invoice(first_invoice))
            first_payloads = [call.args[2] for call in api_request.call_args_list]
            api_request.reset_mock()
            api_request.return_value = {"ok": True, "created": False, "idempotent": True}
            next_result = json.loads(TOOLS.register_credit_card_invoice(next_invoice))
            next_payloads = [call.args[2] for call in api_request.call_args_list]

        self.assertTrue(first_result["ok"])
        self.assertTrue(next_result["ok"])
        self.assertEqual(
            [payload["externalEventId"] for payload in first_payloads[1:]],
            [payload["externalEventId"] for payload in next_payloads],
        )
        self.assertEqual(next_result["createdCount"], 0)
        self.assertEqual(next_result["alreadyRegisteredCount"], 7)
        self.assertTrue(
            all(transaction["status"] == "already_registered" for transaction in next_result["transactions"])
        )

    def test_register_credit_card_invoice_registers_uninstallmented_purchase_at_due_date(self):
        with patch.object(TOOLS, "_api_request", return_value={"ok": True}) as api_request:
            result = json.loads(TOOLS.register_credit_card_invoice({
                "invoice_due_date": "2026-08-10",
                "source_person": "Conjunta",
                "payment_bank": "Itaú",
                "items": [{
                    "description": "Supermercado",
                    "category": "🛒 Mercado",
                    "installment_amount": 250,
                    "current_installment": 1,
                    "total_installments": 1,
                }],
            }))

        self.assertTrue(result["ok"])
        self.assertEqual(result["scheduledCount"], 1)
        _, _, payload = api_request.call_args.args
        self.assertEqual(payload["date"], "2026-08-10")
        self.assertEqual(payload["description"], "Supermercado")
        self.assertEqual(payload["paymentMethod"], "credit")

    def test_register_credit_card_invoice_uses_last_day_when_needed(self):
        with patch.object(TOOLS, "_api_request", return_value={"ok": True}) as api_request:
            result = json.loads(TOOLS.register_credit_card_invoice({
                "invoice_due_date": "2026-01-31",
                "source_person": "Renata",
                "payment_bank": "Inter",
                "items": [{
                    "description": "Curso 1/2",
                    "category": "🎓 Educacao",
                    "installment_amount": 99.9,
                    "current_installment": 1,
                    "total_installments": 2,
                }],
            }))

        self.assertTrue(result["ok"])
        self.assertEqual(
            [call.args[2]["date"] for call in api_request.call_args_list],
            ["2026-01-31", "2026-02-28"],
        )

    def test_register_credit_card_invoice_is_idempotent_when_retried(self):
        args = {
            "invoice_due_date": "2026-08-10",
            "source_person": "Filipe",
            "payment_bank": "Nubank",
            "items": [{
                "description": "Celular 2/4",
                "category": "🧥 Compras",
                "installment_amount": 200,
                "current_installment": 2,
                "total_installments": 4,
            }],
        }
        with patch.object(TOOLS, "_api_request", return_value={"ok": True}) as api_request:
            first = json.loads(TOOLS.register_credit_card_invoice(args))
            first_payloads = [call.args[2] for call in api_request.call_args_list]
            api_request.reset_mock()
            second = json.loads(TOOLS.register_credit_card_invoice(args))
            second_payloads = [call.args[2] for call in api_request.call_args_list]

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(
            [payload["externalEventId"] for payload in first_payloads],
            [payload["externalEventId"] for payload in second_payloads],
        )

    def test_register_credit_card_invoice_rejects_invalid_installment_range(self):
        result = json.loads(TOOLS.register_credit_card_invoice({
            "invoice_due_date": "2026-08-10",
            "source_person": "Filipe",
            "payment_bank": "Nubank",
            "items": [{
                "description": "Compra",
                "category": "🧥 Compras",
                "installment_amount": 100,
                "current_installment": 4,
                "total_installments": 3,
            }],
        }))

        self.assertFalse(result["ok"])
        self.assertIn("nao pode ser maior", result["error"])

    def test_register_credit_card_invoice_preserves_duplicate_details_after_partial_run(self):
        duplicate = {
            "code": "possible_duplicate",
            "error": "Possivel duplicidade encontrada",
            "duplicate": {"id": 12, "description": "Curso 2/3"},
        }
        with patch.object(
            TOOLS,
            "_api_request",
            side_effect=[
                {"ok": True, "created": True, "transaction": {"id": 41}},
                TOOLS.ControllApiError(duplicate["error"], duplicate),
            ],
        ):
            result = json.loads(TOOLS.register_credit_card_invoice({
                "invoice_due_date": "2026-08-10",
                "source_person": "Filipe",
                "payment_bank": "Nubank",
                "items": [{
                    "description": "Curso 1/2",
                    "category": "🎓 Educacao",
                    "installment_amount": 100,
                    "current_installment": 1,
                    "total_installments": 2,
                }],
            }))

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "possible_duplicate")
        self.assertEqual(len(result["completed"]), 1)
        self.assertEqual(result["failed"]["installmentNumber"], 2)

    def test_list_transactions_builds_filters(self):
        with patch.object(TOOLS, "_api_request", return_value={"items": []}) as api_request:
            result = json.loads(TOOLS.list_transactions({
                "month": "2026-08",
                "search": "mercado",
                "source_person": "Renata",
                "limit": 10,
            }))

        self.assertTrue(result["ok"])
        method, path = api_request.call_args.args
        self.assertEqual(method, "GET")
        self.assertIn("month=2026-08", path)
        self.assertIn("sourcePerson=Renata", path)
        self.assertIn("limit=10", path)

    def test_update_transaction_calls_expected_endpoint(self):
        with patch.object(TOOLS, "_api_request", return_value={"transaction": {"id": 42}}) as api_request:
            result = json.loads(TOOLS.update_transaction({
                "transaction_id": 42,
                "amount": 48.5,
                "source_person": "Conjunta",
                "payment_method": "credit",
                "payment_bank": "Banco Inter",
            }))

        self.assertTrue(result["ok"])
        method, path, payload = api_request.call_args.args
        self.assertEqual((method, path), ("PATCH", "/api/integrations/transactions/42"))
        self.assertEqual(payload["amount"], 48.5)
        self.assertEqual(payload["sourcePerson"], "Conjunta")
        self.assertEqual(payload["paymentMethod"], "credit")
        self.assertEqual(payload["paymentBank"], "Banco Inter")

    def test_create_transaction_requires_payment_details(self):
        result = json.loads(TOOLS.create_transaction({
            "date": "2026-08-11",
            "description": "Compra no mercado",
            "category": "🛒 Mercado",
            "type": "expense",
            "amount": 35.9,
            "source_person": "Filipe",
        }))

        self.assertFalse(result["ok"])
        self.assertIn("payment_method", result["error"])

    def test_delete_transaction_requires_explicit_confirmation(self):
        with patch.object(TOOLS, "_api_request", return_value={}) as api_request:
            blocked = json.loads(TOOLS.delete_transaction({
                "transaction_id": 42,
                "confirmed": False,
            }))
            allowed = json.loads(TOOLS.delete_transaction({
                "transaction_id": 42,
                "confirmed": True,
            }))

        self.assertFalse(blocked["ok"])
        self.assertIn("confirmacao explicita", blocked["error"])
        self.assertTrue(allowed["ok"])
        api_request.assert_called_once_with("DELETE", "/api/integrations/transactions/42")

    def test_monthly_report_validates_month(self):
        result = json.loads(TOOLS.monthly_report({"month": "08/2026"}))
        self.assertFalse(result["ok"])
        self.assertIn("YYYY-MM", result["error"])

    def test_monthly_report_calls_expected_endpoint(self):
        with patch.object(TOOLS, "_api_request", return_value={"month": "2026-08"}) as api_request:
            result = json.loads(TOOLS.monthly_report({"month": "2026-08"}))

        self.assertTrue(result["ok"])
        self.assertEqual(
            api_request.call_args.args,
            ("GET", "/api/integrations/reports/monthly?month=2026-08"),
        )


if __name__ == "__main__":
    unittest.main()
