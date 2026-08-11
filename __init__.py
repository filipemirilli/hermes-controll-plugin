"""Registro do plugin oficial de integracao Hermes -> Controll."""

from . import schemas, tools


def register(ctx):
    """Registra as ferramentas nativas que o modelo pode chamar."""
    ctx.register_tool(
        name="controll_create_transaction",
        toolset="controll",
        schema=schemas.CREATE_TRANSACTION,
        handler=tools.create_transaction,
    )
    ctx.register_tool(
        name="controll_monthly_report",
        toolset="controll",
        schema=schemas.MONTHLY_REPORT,
        handler=tools.monthly_report,
    )
