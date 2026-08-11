"""Schemas apresentados ao modelo pelo Hermes Agent."""

CREATE_TRANSACTION = {
    "name": "controll_create_transaction",
    "description": (
        "Registra no Controll uma receita ou despesa informada pelo usuario. "
        "Use somente quando valor, descricao e tipo estiverem claros; pergunte antes "
        "se faltar dado essencial. Nao use para investimentos, resgates, transferencias, "
        "saldo inicial ou ajustes patrimoniais. Categorias de despesa preferenciais: "
        "🏠 Moradia, 🛒 Mercado, 💳 Cartao de Credito, 🍔 Alimentacao, 🚗 Transporte, "
        "💡 Contas, 🏥 Saude, 🎓 Educacao, 🎬 Lazer, 🧥 Compras, ✈️ Viagem e 🐶 Pets. "
        "Categorias de receita preferenciais: 💼 Salario, 💸 Freelance, 🏦 Rendimento, "
        "🎁 Presente, 🧾 Reembolso e 📈 Bonus. Confirme o resultado retornado pela ferramenta."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Data do lancamento em YYYY-MM-DD.",
            },
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
        },
        "required": ["date", "description", "category", "type", "amount"],
        "additionalProperties": False,
    },
}

MONTHLY_REPORT = {
    "name": "controll_monthly_report",
    "description": (
        "Consulta no Controll o resumo financeiro de um mes, incluindo receitas, despesas, "
        "saldo e gastos por categoria. Use quando o usuario pedir relatorio ou resumo mensal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "month": {
                "type": "string",
                "description": "Mes consultado em YYYY-MM.",
            }
        },
        "required": ["month"],
        "additionalProperties": False,
    },
}
