# Hermes Controll Plugin

Plugin nativo do Hermes Agent para integrar mensagens financeiras ao Controll.

## Arquitetura

`Telegram -> Hermes Agent -> plugin controll-finance -> API HTTPS do Controll`

O token e solicitado pelo instalador oficial do Hermes e salvo no `.env` do perfil.
Ele nao deve ser colocado em skills, prompts, arquivos versionados ou conversas.

## Requisitos

- Hermes Agent 0.20.0 ou posterior
- Controll com a integracao `transactions:write,reports:read` configurada
- Variavel secreta `CONTROLL_API_TOKEN`

O endpoint padrao e `https://controll.hzcromos.com.br`. Para outro ambiente, defina
`CONTROLL_API_URL` com uma URL HTTPS.

## Ferramentas

- `controll_create_transaction`: registra receitas e despesas operacionais
- `controll_monthly_report`: consulta o resumo mensal

Investimentos, resgates, transferencias, saldo inicial e ajustes patrimoniais ficam
fora da ferramenta de lancamento para preservar a contabilidade correta.

## Testes

```bash
python -m unittest discover -s tests -v
```
