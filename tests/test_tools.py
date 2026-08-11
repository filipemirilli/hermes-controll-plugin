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
            }))

        self.assertTrue(result["ok"])
        method, path, payload = api_request.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/api/integrations/transactions")
        self.assertEqual(payload["amount"], 35.9)
        self.assertEqual(payload["sourcePerson"], "Filipe")
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
            }))

        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "possible_duplicate")
        self.assertEqual(result["duplicate"]["id"], 12)

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
            }))

        self.assertTrue(result["ok"])
        method, path, payload = api_request.call_args.args
        self.assertEqual((method, path), ("PATCH", "/api/integrations/transactions/42"))
        self.assertEqual(payload["amount"], 48.5)
        self.assertEqual(payload["sourcePerson"], "Conjunta")

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
