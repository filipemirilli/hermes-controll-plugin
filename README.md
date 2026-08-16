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

O endpoint padrao e `https://controll.cromoz.com.br`. Para outro ambiente, defina
`CONTROLL_API_URL` com uma URL HTTPS.

## Ferramentas

- `controll_create_transaction`: registra receitas e despesas operacionais, incluindo forma de pagamento e banco
- `controll_register_credit_card_invoice`: registra todos os itens de uma fatura de cartao no vencimento e agenda somente as parcelas futuras
- `controll_list_transactions`: localiza lancamentos feitos pelo Hermes
- `controll_update_transaction`: corrige um lancamento feito pelo Hermes
- `controll_delete_transaction`: exclui um lancamento apos confirmacao explicita
- `controll_monthly_report`: consulta o resumo mensal

O plugin identifica Filipe, Renata ou Conjunta, forma de pagamento (debito, credito ou
Pix) e o banco utilizado. Se algum desses dados nao estiver claro na mensagem, ele pede
uma confirmacao objetiva em vez de inventar. Tambem bloqueia repeticoes exatas ate que o
usuario confirme que o segundo lancamento e realmente desejado.

Para faturas de cartao, o Hermes usa o vencimento mostrado na propria fatura como a data
de desembolso. Uma compra `3/10` em uma fatura que vence em 10/08 cria `3/10` em 10/08 e
somente `4/10` a `10/10` nos vencimentos futuros. Parcelas anteriores nunca sao criadas e
o pagamento total da fatura nao e registrado como uma despesa adicional, evitando dupla
contagem. Ao receber a fatura seguinte, as parcelas que ja estavam programadas sao
conferidas pelo identificador estavel e retornam como ja registradas, sem criar uma segunda
despesa.

Investimentos, aportes, resgates, transferencias, saldo inicial e ajustes patrimoniais
ficam fora da ferramenta para preservar a contabilidade correta.
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
