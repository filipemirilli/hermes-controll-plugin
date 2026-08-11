"""Handlers HTTP do plugin Hermes -> Controll, sem dependencias externas."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://controll.hzcromos.com.br"
MAX_RESPONSE_BYTES = 1_000_000
RETRYABLE_STATUS = {502, 503, 504}


class _NoRedirect(request.HTTPRedirectHandler):
    """Evita que o bearer token seja encaminhado por redirecionamentos."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        del req, fp, code, msg, headers, newurl
        return None


def _json_result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _base_url() -> str:
    value = os.getenv("CONTROLL_API_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("CONTROLL_API_URL deve ser uma URL HTTPS valida")
    return value


def _token() -> str:
    value = os.getenv("CONTROLL_API_TOKEN", "").strip()
    if not value:
        raise ValueError("CONTROLL_API_TOKEN nao foi configurado")
    return value


def _decode_response(raw: bytes) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("O Controll retornou uma resposta invalida") from exc
    if not isinstance(payload, dict):
        raise ValueError("O Controll retornou um formato inesperado")
    return payload


def _read_limited(response) -> bytes:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("A resposta do Controll excedeu o limite permitido")
    return raw


def _api_request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{_base_url()}{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {_token()}",
        "User-Agent": "hermes-controll-plugin/1.0.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    opener = request.build_opener(_NoRedirect())
    last_error = None
    for attempt in range(2):
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with opener.open(req, timeout=15) as response:
                return _decode_response(_read_limited(response))
        except error.HTTPError as exc:
            try:
                error_payload = _decode_response(_read_limited(exc))
            except ValueError:
                error_payload = {}
            message = str(error_payload.get("error") or f"Erro HTTP {exc.code} no Controll")
            if exc.code in RETRYABLE_STATUS and attempt == 0:
                last_error = message
                time.sleep(0.25)
                continue
            raise ValueError(message) from exc
        except error.URLError as exc:
            last_error = "Nao foi possivel conectar ao Controll"
            if attempt == 0:
                time.sleep(0.25)
                continue
            raise ValueError(last_error) from exc

    raise ValueError(last_error or "Falha inesperada ao acessar o Controll")


def _valid_iso_date(value: object) -> str:
    text = str(value or "").strip()
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("date deve estar em YYYY-MM-DD") from exc
    return text


def _valid_month(value: object) -> str:
    text = str(value or "").strip()
    if len(text) != 7 or text[4] != "-":
        raise ValueError("month deve estar em YYYY-MM")
    try:
        date.fromisoformat(f"{text}-01")
    except ValueError as exc:
        raise ValueError("month deve estar em YYYY-MM") from exc
    return text


def _positive_amount(value: object) -> float:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount deve ser um valor numerico positivo") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount deve ser um valor numerico positivo")
    return float(amount)


def create_transaction(args: dict, **kwargs) -> str:
    """Cria uma receita/despesa operacional no Controll."""
    del kwargs
    try:
        description = str(args.get("description") or "").strip()
        category = str(args.get("category") or "").strip()
        transaction_type = str(args.get("type") or "").strip().lower()
        if not description:
            raise ValueError("description e obrigatoria")
        if not category:
            raise ValueError("category e obrigatoria")
        if transaction_type not in {"income", "expense"}:
            raise ValueError("type deve ser income ou expense")

        external_event_id = f"hermes-plugin-{uuid.uuid4()}"
        payload = {
            "externalEventId": external_event_id,
            "date": _valid_iso_date(args.get("date")),
            "description": description,
            "category": category,
            "type": transaction_type,
            "amount": _positive_amount(args.get("amount")),
        }
        result = _api_request("POST", "/api/integrations/transactions", payload)
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:  # handlers nunca propagam excecoes ao loop do agente
        return _json_result({"ok": False, "error": str(exc)})


def monthly_report(args: dict, **kwargs) -> str:
    """Consulta o resumo financeiro operacional de um mes."""
    del kwargs
    try:
        month = _valid_month(args.get("month"))
        query = parse.urlencode({"month": month})
        result = _api_request("GET", f"/api/integrations/reports/monthly?{query}")
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:  # handlers nunca propagam excecoes ao loop do agente
        return _json_result({"ok": False, "error": str(exc)})
