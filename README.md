# MT5TITAN

Laboratório de trading quantitativo e automação com MetaTrader 5, criado como evolução arquitetural do Projeto-MT5.

> Estado atual: fundação arquitetural. Nenhuma estratégia ou IA está autorizada a operar capital real.

## Princípios

1. **IA não envia ordens diretamente.**
2. **Risco é soberano:** qualquer sinal pode ser vetado.
3. **Signal, Risk e Execution são camadas separadas.**
4. **Paper/Demo antes de qualquer execução real.**
5. **Toda decisão deve ser auditável e reproduzível.**
6. **Holdout não é reutilizado para ajuste de estratégia.**
7. **Resultado incerto de execução bloqueia novas ordens até reconciliação.**

## Fluxo alvo

```text
Market Data
   ↓
Market Snapshot
   ↓
Strategies / Quant Models
   ↓
AI Committee (futuro)
   ↓
Decision Engine
   ↓
Risk Engine
   ↓
Execution Policy
   ↓
Reconciliation
   ↓
Preflight / order_check
   ↓
Execution Gateway
   ↓
MT5 Demo
```

## Estrutura inicial

```text
src/mt5titan/
├── domain/
├── market/
├── risk/
└── execution/

tests/
docs/
```

## Objetivo

Construir um sistema que permita comparar de forma mensurável:

- baseline quantitativo;
- estratégia quantitativa;
- quant + agente de IA;
- quant + múltiplos agentes;
- diferentes regimes de mercado.

A IA só permanece no fluxo se demonstrar ganho fora da amostra depois de custos.

## Segurança

O repositório nasce sem integração de ordem real. A futura execução Demo manterá as barreiras já experimentadas no Projeto-MT5: autorização explícita, `order_check`, journal persistente, reconciliação, kill switch e limites de perda/exposição.

Veja [docs/ROADMAP.md](docs/ROADMAP.md).
