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
