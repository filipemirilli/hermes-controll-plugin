"""Handlers HTTP do plugin Hermes -> Controll, sem dependencias externas."""

from __future__ import annotations

import json
import os
import time
import unicodedata
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://controll.cromoz.com.br"
MAX_RESPONSE_BYTES = 1_000_000
RETRYABLE_STATUS = {502, 503, 504}
SOURCE_PEOPLE = {"filipe": "Filipe", "renata": "Renata", "conjunta": "Conjunta"}
PAYMENT_METHODS = {
    "debit": "debit",
    "debito": "debit",
    "débito": "debit",
    "credit": "credit",
    "credito": "credit",
    "crédito": "credit",
    "pix": "pix",
}


class ControllApiError(ValueError):
    """Erro HTTP estruturado retornado pelo Controll."""

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


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
        "User-Agent": "hermes-controll-plugin/1.2.0",
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
            raise ControllApiError(message, error_payload) from exc
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


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} deve ser um numero inteiro positivo")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} deve ser um numero inteiro positivo") from exc
    if parsed <= 0:
        raise ValueError(f"{field} deve ser um numero inteiro positivo")
    return parsed


def _source_person(value: object) -> str:
    person = SOURCE_PEOPLE.get(str(value or "").strip().casefold())
    if not person:
        raise ValueError("source_person deve ser Filipe, Renata ou Conjunta")
    return person


def _payment_method(value: object) -> str:
    method = PAYMENT_METHODS.get(str(value or "").strip().casefold())
    if not method:
        raise ValueError("payment_method deve ser debit, credit ou pix")
    return method


def _payment_bank(value: object) -> str:
    bank = " ".join(str(value or "").split())
    if not bank or len(bank) > 120:
        raise ValueError("payment_bank e obrigatorio e deve ter no maximo 120 caracteres")
    return bank


def _normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).split())


def _reject_non_operational(description: object, category: object) -> None:
    normalized_category = _normalized_text(category)
    normalized_description = _normalized_text(description)
    blocked_categories = ("investimento", "transferencia", "aporte", "resgate")
    blocked_descriptions = (
        "pagamento de fatura",
        "fatura do cartao",
        "saldo inicial",
        "ajuste patrimonial",
        "transferencia entre contas",
        "aporte em investimento",
        "resgate de investimento",
    )
    if any(term in normalized_category for term in blocked_categories) or any(
        term in normalized_description for term in blocked_descriptions
    ):
        raise ValueError(
            "Investimentos, aportes, resgates, transferencias, pagamento de fatura, "
            "saldo inicial e ajustes devem ser feitos manualmente no Controll"
        )


def _api_error_result(exc: Exception) -> str:
    if isinstance(exc, ControllApiError):
        payload = dict(exc.payload)
        payload.setdefault("ok", False)
        payload.setdefault("error", str(exc))
        return _json_result(payload)
    return _json_result({"ok": False, "error": str(exc)})


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
        _reject_non_operational(description, category)

        external_event_id = f"hermes-plugin-{uuid.uuid4()}"
        payload = {
            "externalEventId": external_event_id,
            "date": _valid_iso_date(args.get("date")),
            "description": description,
            "category": category,
            "type": transaction_type,
            "amount": _positive_amount(args.get("amount")),
            "sourcePerson": _source_person(args.get("source_person")),
            "paymentMethod": _payment_method(args.get("payment_method")),
            "paymentBank": _payment_bank(args.get("payment_bank")),
            "allowDuplicate": bool(args.get("allow_duplicate", False)),
        }
        result = _api_request("POST", "/api/integrations/transactions", payload)
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:  # handlers nunca propagam excecoes ao loop do agente
        return _api_error_result(exc)


def list_transactions(args: dict, **kwargs) -> str:
    """Lista lancamentos operacionais criados pelo cliente Hermes."""
    del kwargs
    try:
        query = {}
        month = str(args.get("month") or "").strip()
        search = str(args.get("search") or "").strip()
        source_person = str(args.get("source_person") or "").strip()
        if month:
            query["month"] = _valid_month(month)
        if search:
            query["search"] = search[:120]
        if source_person:
            query["sourcePerson"] = _source_person(source_person)
        if args.get("limit") is not None:
            limit = _positive_int(args.get("limit"), "limit")
            if limit > 50:
                raise ValueError("limit deve estar entre 1 e 50")
            query["limit"] = limit
        path = "/api/integrations/transactions"
        if query:
            path = f"{path}?{parse.urlencode(query)}"
        result = _api_request("GET", path)
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:
        return _api_error_result(exc)


def update_transaction(args: dict, **kwargs) -> str:
    """Corrige um lancamento criado pelo cliente Hermes."""
    del kwargs
    try:
        transaction_id = _positive_int(args.get("transaction_id"), "transaction_id")
        payload = {}
        if "date" in args:
            payload["date"] = _valid_iso_date(args.get("date"))
        if "description" in args:
            description = str(args.get("description") or "").strip()
            if not description:
                raise ValueError("description e obrigatoria")
            payload["description"] = description
        if "category" in args:
            category = str(args.get("category") or "").strip()
            if not category:
                raise ValueError("category e obrigatoria")
            payload["category"] = category
        if "type" in args:
            transaction_type = str(args.get("type") or "").strip().lower()
            if transaction_type not in {"income", "expense"}:
                raise ValueError("type deve ser income ou expense")
            payload["type"] = transaction_type
        if "amount" in args:
            payload["amount"] = _positive_amount(args.get("amount"))
        if "source_person" in args:
            payload["sourcePerson"] = _source_person(args.get("source_person"))
        if "payment_method" in args:
            payload["paymentMethod"] = _payment_method(args.get("payment_method"))
        if "payment_bank" in args:
            payload["paymentBank"] = _payment_bank(args.get("payment_bank"))
        payload["allowDuplicate"] = bool(args.get("allow_duplicate", False))
        if len(payload) == 1:
            raise ValueError("Informe ao menos um campo para corrigir")
        _reject_non_operational(payload.get("description"), payload.get("category"))
        result = _api_request(
            "PATCH",
            f"/api/integrations/transactions/{transaction_id}",
            payload,
        )
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:
        return _api_error_result(exc)


def delete_transaction(args: dict, **kwargs) -> str:
    """Exclui um lancamento criado pelo cliente Hermes apos confirmacao."""
    del kwargs
    try:
        transaction_id = _positive_int(args.get("transaction_id"), "transaction_id")
        if args.get("confirmed") is not True:
            raise ValueError("A exclusao exige confirmacao explicita do usuario")
        result = _api_request(
            "DELETE",
            f"/api/integrations/transactions/{transaction_id}",
        )
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:
        return _api_error_result(exc)


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
        return _api_error_result(exc)
