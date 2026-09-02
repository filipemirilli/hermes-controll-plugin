"""Handlers HTTP do plugin Hermes -> Controll, sem dependencias externas."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import time
import unicodedata
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://controll.cromoz.com.br"
PLUGIN_VERSION = "1.4.1"
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
        "User-Agent": f"hermes-controll-plugin/{PLUGIN_VERSION}",
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
    raw = re.sub(r"[\s_-]+", " ", str(value or "").strip().casefold())
    aliases = {
        **PAYMENT_METHODS,
        "cartao de debito": "debit",
        "cartão de débito": "debit",
        "cartao debito": "debit",
        "cartão débito": "debit",
        "debit card": "debit",
        "cartao de credito": "credit",
        "cartão de crédito": "credit",
        "cartao credito": "credit",
        "cartão crédito": "credit",
        "credit card": "credit",
    }
    method = aliases.get(raw)
    if not method:
        raise ValueError("payment_method deve ser debit, credit ou pix")
    return method


def _payment_bank(value: object) -> str:
    bank = " ".join(str(value or "").split())
    if not bank or len(bank) > 120:
        raise ValueError("payment_bank e obrigatorio e deve ter no maximo 120 caracteres")
    return bank


def _tool_argument(args: dict, snake_case: str, camel_case: str) -> object:
    """Aceita os dois formatos usados por diferentes runtimes do Hermes."""
    if snake_case in args:
        return args.get(snake_case)
    return args.get(camel_case)


def _add_months_to_iso(iso_date: str, months: int) -> str:
    """Avanca meses preservando o dia ou o ultimo dia do mes, se necessario."""
    original = date.fromisoformat(iso_date)
    target_index = (original.year * 12 + original.month - 1) + months
    target_year, target_month_index = divmod(target_index, 12)
    target_month = target_month_index + 1
    target_day = min(original.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day).isoformat()


def _invoice_item_description(
    description: str,
    current_installment: int,
    total_installments: int,
    installment_number: int,
) -> str:
    """Mantem o identificador X/Y da parcela coerente em cada mes."""
    if total_installments == 1:
        return description

    replacement = f"{installment_number}/{total_installments}"
    number_patterns = (
        rf"(?<!\d)0*{current_installment}\s*/\s*0*{total_installments}(?!\d)",
        rf"(?<!\d)\d{{1,3}}\s*/\s*0*{total_installments}(?!\d)",
    )
    for number_pattern in number_patterns:
        updated, replacements = re.subn(number_pattern, replacement, description, count=1)
        if replacements:
            return updated
    return f"{description} ({replacement})"


def _invoice_line_key(
    description: str,
    category: str,
    amount: float,
    current_installment: int,
    total_installments: int,
) -> str:
    """Cria uma chave estavel para diferenciar linhas repetidas da mesma fatura."""
    payload = {
        "description": description,
        "category": category,
        "amount": amount,
        "currentInstallment": current_installment,
        "totalInstallments": total_installments,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _invoice_event_id(
    *,
    due_date: str,
    description: str,
    category: str,
    amount: float,
    source_person: str,
    payment_bank: str,
    installment_number: int,
    total_installments: int,
    occurrence: int,
) -> str:
    """Gera idempotencia por parcela, inclusive se a ferramenta for repetida."""
    canonical = {
        "date": due_date,
        "description": description,
        "category": category,
        "amount": amount,
        "sourcePerson": source_person,
        "paymentMethod": "credit",
        "paymentBank": payment_bank,
        "installmentNumber": installment_number,
        "totalInstallments": total_installments,
        "occurrence": occurrence,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"hermes-controll-invoice-{digest}"


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
            "paymentMethod": _payment_method(
                _tool_argument(args, "payment_method", "paymentMethod")
            ),
            "paymentBank": _payment_bank(
                _tool_argument(args, "payment_bank", "paymentBank")
            ),
            "allowDuplicate": bool(args.get("allow_duplicate", False)),
        }
        result = _api_request("POST", "/api/integrations/transactions", payload)
        result.setdefault("ok", True)
        return _json_result(result)
    except Exception as exc:  # handlers nunca propagam excecoes ao loop do agente
        return _api_error_result(exc)


def register_credit_card_invoice(args: dict, **kwargs) -> str:
    """Registra os itens de uma fatura na data de vencimento, incluindo parcelas futuras."""
    del kwargs
    try:
        invoice_due_date = _valid_iso_date(args.get("invoice_due_date"))
        source_person = _source_person(args.get("source_person"))
        payment_bank = _payment_bank(args.get("payment_bank"))
        allow_duplicate = bool(args.get("allow_duplicate", False))
        raw_items = args.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("items deve conter ao menos uma compra da fatura")
        if len(raw_items) > 100:
            raise ValueError("A fatura pode conter no maximo 100 compras por vez")

        line_occurrences: dict[str, int] = {}
        scheduled = []
        created_count = 0
        already_registered_count = 0
        for item_index, raw_item in enumerate(raw_items, start=1):
            if not isinstance(raw_item, dict):
                raise ValueError(f"items[{item_index}] deve ser uma compra valida")

            description = str(raw_item.get("description") or "").strip()
            category = str(raw_item.get("category") or "").strip()
            if not description or len(description) > 500:
                raise ValueError(f"items[{item_index}].description e obrigatoria e limitada a 500 caracteres")
            if not category or len(category) > 120:
                raise ValueError(f"items[{item_index}].category e obrigatoria e limitada a 120 caracteres")
            _reject_non_operational(description, category)

            amount = _positive_amount(raw_item.get("installment_amount"))
            current_installment = _positive_int(
                raw_item.get("current_installment"),
                f"items[{item_index}].current_installment",
            )
            total_installments = _positive_int(
                raw_item.get("total_installments"),
                f"items[{item_index}].total_installments",
            )
            if total_installments > 360:
                raise ValueError(f"items[{item_index}].total_installments esta limitado a 360")
            if current_installment > total_installments:
                raise ValueError(
                    f"items[{item_index}].current_installment nao pode ser maior que total_installments"
                )

            line_key = _invoice_line_key(
                description,
                category,
                amount,
                current_installment,
                total_installments,
            )
            occurrence = line_occurrences.get(line_key, 0) + 1
            line_occurrences[line_key] = occurrence

            for offset, installment_number in enumerate(
                range(current_installment, total_installments + 1)
            ):
                scheduled_date = _add_months_to_iso(invoice_due_date, offset)
                scheduled_description = _invoice_item_description(
                    description,
                    current_installment,
                    total_installments,
                    installment_number,
                )
                payload = {
                    "externalEventId": _invoice_event_id(
                        due_date=scheduled_date,
                        description=scheduled_description,
                        category=category,
                        amount=amount,
                        source_person=source_person,
                        payment_bank=payment_bank,
                        installment_number=installment_number,
                        total_installments=total_installments,
                        occurrence=occurrence,
                    ),
                    "date": scheduled_date,
                    "description": scheduled_description,
                    "category": category,
                    "type": "expense",
                    "amount": amount,
                    "sourcePerson": source_person,
                    "paymentMethod": "credit",
                    "paymentBank": payment_bank,
                    "allowDuplicate": allow_duplicate,
                }
                try:
                    result = _api_request("POST", "/api/integrations/transactions", payload)
                except Exception as exc:
                    error_payload = dict(exc.payload) if isinstance(exc, ControllApiError) else {}
                    error_payload.update({
                        "ok": False,
                        "error": str(exc),
                        "invoiceDueDate": invoice_due_date,
                        "completed": scheduled,
                        "failed": {
                            "itemIndex": item_index,
                            "description": scheduled_description,
                            "installmentNumber": installment_number,
                            "totalInstallments": total_installments,
                            "date": scheduled_date,
                        },
                    })
                    return _json_result(error_payload)

                transaction = result.get("transaction") if isinstance(result, dict) else None
                idempotent = bool(result.get("idempotent", False))
                created = bool(result.get("created", True))
                if idempotent:
                    already_registered_count += 1
                elif created:
                    created_count += 1
                scheduled.append({
                    "itemIndex": item_index,
                    "description": scheduled_description,
                    "installmentNumber": installment_number,
                    "totalInstallments": total_installments,
                    "date": scheduled_date,
                    "status": "already_registered" if idempotent else "created",
                    "created": created,
                    "idempotent": idempotent,
                    "transactionId": transaction.get("id") if isinstance(transaction, dict) else None,
                })

        return _json_result({
            "ok": True,
            "invoiceDueDate": invoice_due_date,
            "paymentMethod": "credit",
            "paymentBank": payment_bank,
            "scheduledCount": len(scheduled),
            "createdCount": created_count,
            "alreadyRegisteredCount": already_registered_count,
            "transactions": scheduled,
        })
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
