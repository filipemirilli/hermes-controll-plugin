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
            }))

        self.assertTrue(result["ok"])
        method, path, payload = api_request.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/api/integrations/transactions")
        self.assertEqual(payload["amount"], 35.9)
        self.assertTrue(payload["externalEventId"].startswith("hermes-plugin-"))

    def test_create_transaction_rejects_investment_type(self):
        result = json.loads(TOOLS.create_transaction({
            "date": "2026-08-11",
            "description": "Aplicacao",
            "category": "Investimento",
            "type": "investment",
            "amount": 100,
        }))
        self.assertFalse(result["ok"])
        self.assertIn("income ou expense", result["error"])

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
