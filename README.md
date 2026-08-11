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
- `controll_list_transactions`: localiza lancamentos feitos pelo Hermes
- `controll_update_transaction`: corrige um lancamento feito pelo Hermes
- `controll_delete_transaction`: exclui um lancamento apos confirmacao explicita
- `controll_monthly_report`: consulta o resumo mensal

O plugin identifica Filipe, Renata ou Conjunta e bloqueia repeticoes exatas ate que o
usuario confirme que o segundo lancamento e realmente desejado.

Investimentos, aportes, resgates, transferencias, pagamento de fatura, saldo inicial e
ajustes patrimoniais ficam fora da ferramenta para preservar a contabilidade correta.
Esses registros continuam sendo feitos manualmente no Controll.

## Migracao do perfil financeiro

Depois da ativacao, o Controll deve ser a unica fonte ativa dos lancamentos. O banco
SQLite e os relatorios antigos do Hermes devem permanecer somente como arquivo historico
de leitura. Pause os crons antigos antes de usar o plugin em producao, evitando que os dois
sistemas continuem registrando ou enviando relatorios diferentes.

As orientacoes prontas para substituir as regras financeiras antigas estao em
[`PROFILE_FINANCEIRO_CONTROLL.md`](PROFILE_FINANCEIRO_CONTROLL.md).

## Testes

```bash
python -m unittest discover -s tests -v
```
