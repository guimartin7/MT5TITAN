# MT5TITAN — Roadmap

## Fase 0 — Fundação
- [x] Estrutura de pacote Python
- [x] Contratos MarketSnapshot / Signal / Decision / RiskDecision
- [x] Risk Engine central
- [x] Política de execução independente da corretora
- [x] Reconciliação pura e testável
- [x] Testes unitários iniciais

## Fase 1 — Migração segura do Projeto-MT5
- [ ] Adapter MetaTrader5
- [ ] Feed health + coletor de candles fechados
- [ ] Instrument profiles (Forex/B3)
- [ ] Execution journal
- [ ] Preflight Demo
- [ ] Recovery de execução UNKNOWN
- [ ] Paper broker unificado

## Fase 2 — Research Engine
- [ ] Backtest compartilhado
- [ ] Custos/slippage por instrumento
- [ ] Estratégias SMA, momentum e mean reversion
- [ ] Split development/validation/holdout
- [ ] Walk-forward
- [ ] Stress tests
- [ ] Métricas: expectancy, profit factor, Sharpe, Sortino, Calmar, max DD

## Fase 3 — Market Intelligence
- [ ] Feature pipeline
- [ ] Regime detector
- [ ] Market score por ativo
- [ ] Correlação/exposição de portfólio
- [ ] Calendário econômico

## Fase 4 — Titan Intelligence
- [ ] Technical agent
- [ ] News agent
- [ ] Macro agent
- [ ] AI committee
- [ ] Saída estruturada por schema
- [ ] Pesos calibrados somente com dados de desenvolvimento/validação
- [ ] Comparação Quant vs Quant+IA

## Fase 5 — Operação supervisionada
- [ ] Paper trading contínuo
- [ ] Dashboard explicável por decision_id
- [ ] MT5 Demo com autorização explícita
- [ ] Kill switch
- [ ] Reconciliation antes/depois da execução
- [ ] Promoção somente após critérios objetivos pré-definidos

## Regra de ouro

Nenhuma IA, estratégia ou dashboard recebe acesso direto a `order_send`.
O gateway de execução é o único componente autorizado a falar com a API de ordem.
