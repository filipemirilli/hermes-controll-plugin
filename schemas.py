"""Schemas apresentados ao modelo pelo Hermes Agent."""

_CATEGORIES = (
    "Categorias de despesa preferenciais: 🏠 Moradia, 🛒 Mercado, "
    "💳 Cartao de Credito, 🍔 Alimentacao, 🚗 Transporte, 💡 Contas, "
    "🏥 Saude, 🎓 Educacao, 🎬 Lazer, 🧥 Compras, ✈️ Viagem e 🐶 Pets. "
    "Categorias de receita preferenciais: 💼 Salario, 💸 Freelance, "
    "🏦 Rendimento, 🎁 Presente, 🧾 Reembolso e 📈 Bonus."
)

_OPERATIONAL_ONLY = (
    "Nao use para investimentos, aportes, resgates, transferencias entre contas, "
    "pagamento de fatura, saldo inicial ou ajustes patrimoniais; essas operacoes "
    "devem ser feitas manualmente no Controll."
)

CREATE_TRANSACTION = {
    "name": "controll_create_transaction",
    "description": (
        "Registra no Controll uma receita ou despesa operacional informada pelo usuario. "
        "Use somente quando valor, descricao, data, tipo e pessoa estiverem claros. "
        "Se a API indicar possible_duplicate, mostre o lancamento existente e somente "
        "repita com allow_duplicate=true depois de confirmacao explicita do usuario. "
        f"{_OPERATIONAL_ONLY} {_CATEGORIES} Confirme apenas o resultado retornado pela ferramenta."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Data em YYYY-MM-DD."},
            "description": {
                "type": "string",
                "description": "Descricao objetiva do que foi recebido ou pago.",
            },
            "category": {
                "type": "string",
                "description": "Categoria financeira, preferencialmente uma categoria padrao do Controll.",
            },
            "type": {
                "type": "string",
                "enum": ["income", "expense"],
                "description": "income para receita; expense para despesa.",
            },
            "amount": {
                "type": "number",
                "exclusiveMinimum": 0,
                "description": "Valor positivo em reais, sem simbolo monetario.",
            },
            "source_person": {
                "type": "string",
                "enum": ["Filipe", "Renata", "Conjunta"],
                "description": (
                    "Pessoa responsavel pelo lancamento. Use Conjunta para despesas da casa "
                    "como agua, luz, gas, internet, condominio e IPTU."
                ),
            },
            "payment_method": {
                "type": "string",
                "enum": ["debit", "credit", "pix"],
                "description": "Forma de pagamento: debit para debito, credit para credito ou pix.",
            },
            "payment_bank": {
                "type": "string",
                "description": "Banco, instituicao ou carteira usada no pagamento, por exemplo Nubank.",
            },
            "allow_duplicate": {
                "type": "boolean",
                "description": (
                    "Use true somente depois que o usuario confirmar explicitamente que um "
                    "lancamento apontado como duplicado deve ser criado novamente."
                ),
                "default": False,
            },
        },
        "required": ["date", "description", "category", "type", "amount", "source_person", "payment_method", "payment_bank"],
        "additionalProperties": False,
    },
}

REGISTER_CREDIT_CARD_INVOICE = {
    "name": "controll_register_credit_card_invoice",
    "description": (
        "Registra as compras de uma fatura de cartao de credito que tenha vencimento visivel. "
        "Use obrigatoriamente para itens extraidos de uma fatura, inclusive compras sem parcelas "
        "(informe 1/1). Cada compra atual entra na data de vencimento da fatura; para X/Y, a "
        "ferramenta tambem cria somente X/Y ate Y/Y nos meses futuros. Nunca cria parcelas "
        "anteriores e nunca registra um item extra chamado pagamento de fatura. Em toda nova "
        "fatura, cada item e conferido com os lancamentos programados: uma parcela ja registrada "
        "retorna como already_registered e nao e duplicada. O valor de cada item e o valor de UMA "
        "parcela, nao o total original da compra. Se a API indicar "
        "possible_duplicate, mostre o item existente e execute novamente com allow_duplicate=true "
        "somente depois da confirmacao explicita do usuario. "
        f"{_CATEGORIES} Confirme apenas o resultado retornado pela ferramenta."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "invoice_due_date": {
                "type": "string",
                "description": "Data de vencimento mostrada na fatura, em YYYY-MM-DD.",
            },
            "source_person": {
                "type": "string",
                "enum": ["Filipe", "Renata", "Conjunta"],
                "description": "Titular responsavel pelas compras desta fatura.",
            },
            "payment_bank": {
                "type": "string",
                "description": "Banco ou instituicao emissora do cartao, por exemplo Nubank.",
            },
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 100,
                "description": "Todas as compras operacionais identificadas na fatura.",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Descricao objetiva da compra, sem usar Pagamento de fatura.",
                        },
                        "category": {
                            "type": "string",
                            "description": "Categoria financeira da compra.",
                        },
                        "installment_amount": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                            "description": "Valor de uma parcela ou, em 1/1, o valor total da compra.",
                        },
                        "current_installment": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 360,
                            "description": "Numero da parcela que aparece nesta fatura; use 1 para compra sem parcelas.",
                        },
                        "total_installments": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 360,
                            "description": "Total de parcelas; use 1 para compra sem parcelas.",
                        },
                    },
                    "required": [
                        "description",
                        "category",
                        "installment_amount",
                        "current_installment",
                        "total_installments",
                    ],
                    "additionalProperties": False,
                },
            },
            "allow_duplicate": {
                "type": "boolean",
                "description": (
                    "Use true somente depois que o usuario confirmar explicitamente que os itens "
                    "apontados como duplicados devem ser registrados."
                ),
                "default": False,
            },
        },
        "required": ["invoice_due_date", "source_person", "payment_bank", "items"],
        "additionalProperties": False,
    },
}

LIST_TRANSACTIONS = {
    "name": "controll_list_transactions",
    "description": (
        "Lista lancamentos recentes criados pelo Hermes no Controll. Use antes de corrigir "
        "ou excluir para localizar o ID correto. Nao lista lancamentos manuais."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "month": {"type": "string", "description": "Mes opcional em YYYY-MM."},
            "search": {"type": "string", "description": "Texto opcional da descricao ou categoria."},
            "source_person": {
                "type": "string",
                "enum": ["Filipe", "Renata", "Conjunta"],
                "description": "Filtro opcional de pessoa.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Quantidade maxima de resultados; padrao 20.",
            },
        },
        "additionalProperties": False,
    },
}

UPDATE_TRANSACTION = {
    "name": "controll_update_transaction",
    "description": (
        "Corrige um lancamento criado anteriormente pelo Hermes. Primeiro localize o ID com "
        "controll_list_transactions. Nao altera lancamentos manuais nem movimentacoes patrimoniais. "
        f"{_OPERATIONAL_ONLY}"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "integer", "minimum": 1, "description": "ID do lancamento."},
            "date": {"type": "string", "description": "Nova data em YYYY-MM-DD."},
            "description": {"type": "string", "description": "Nova descricao."},
            "category": {"type": "string", "description": "Nova categoria."},
            "type": {"type": "string", "enum": ["income", "expense"]},
            "amount": {"type": "number", "exclusiveMinimum": 0},
            "source_person": {
                "type": "string",
                "enum": ["Filipe", "Renata", "Conjunta"],
            },
            "payment_method": {
                "type": "string",
                "enum": ["debit", "credit", "pix"],
            },
            "payment_bank": {
                "type": "string",
                "description": "Novo banco, instituicao ou carteira usada no pagamento.",
            },
            "allow_duplicate": {
                "type": "boolean",
                "description": "Use true somente apos confirmacao explicita de duplicidade.",
                "default": False,
            },
        },
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
}

DELETE_TRANSACTION = {
    "name": "controll_delete_transaction",
    "description": (
        "Exclui um lancamento criado pelo Hermes. Primeiro localize o ID e mostre ao usuario "
        "o item que sera excluido. Execute somente apos confirmacao explicita."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "transaction_id": {"type": "integer", "minimum": 1, "description": "ID do lancamento."},
            "confirmed": {
                "type": "boolean",
                "description": "Deve ser true somente quando o usuario confirmou a exclusao.",
            },
        },
        "required": ["transaction_id", "confirmed"],
        "additionalProperties": False,
    },
}

MONTHLY_REPORT = {
    "name": "controll_monthly_report",
    "description": (
        "Consulta no Controll o resumo financeiro de um mes, incluindo receitas, despesas, "
        "saldo, gastos por categoria e totais por pessoa."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "month": {"type": "string", "description": "Mes consultado em YYYY-MM."}
        },
        "required": ["month"],
        "additionalProperties": False,
    },
}
