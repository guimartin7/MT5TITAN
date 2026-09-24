# MT5TITAN — Roadmap

## Fase 0 — Fundação
- [x] Estrutura de pacote Python
- [x] Contratos MarketSnapshot / Signal / Decision / RiskDecision
- [x] Risk Engine central
- [x] Política de execução independente da corretora
- [x] Reconciliação pura e testável
- [x] Testes unitários iniciais

## Fase 1 — Migração segura do Projeto-MT5
- [x] Adapter MetaTrader5
- [x] Feed health com normalização do relógio do servidor
- [x] Instrument profiles (base B3; Forex será expandido junto do Research Engine)
- [x] Execution journal idempotente
- [x] Preflight Demo sem order_send
- [x] Recovery conservador de execução UNKNOWN
- [x] Paper broker unificado
- [ ] Gateway Demo final — migrar somente depois do Research Engine estar estável

## Fase 2 — Research Engine
- [x] Backtest compartilhado
- [x] Custos/spread por cenários fixos; slippage específico de instrumento segue na integração B3
- [x] Estratégias SMA, momentum e mean reversion
- [x] Split development/validation/holdout
- [x] Walk-forward
- [x] Stress tests
- [x] Métricas: expectancy, profit factor, Sharpe, Sortino, Calmar, max DD
- [x] Comparação reproduzível contra baseline

## Fase 3 — Market Intelligence
- [x] Feature pipeline com candles fechados
- [x] Regime detector
- [x] Market score por ativo
- [x] Decision Engine determinístico e sensível a regime
- [x] Correlação/exposição de portfólio
- [x] Contratos e gate de risco do calendário econômico; adapter de provedor externo fica para a Fase 4

## Fase 4 — Titan Intelligence
- [x] Technical agent (provider-agnostic)
- [x] News agent (provider-agnostic)
- [x] Macro agent (provider-agnostic)
- [x] AI committee com pesos explícitos e veto
- [x] Saída estruturada por schema
- [x] Provider OpenAI isolado com chave/modelo por ambiente
- [x] Replay persistente para evitar novas chamadas no benchmark
- [ ] Pesos calibrados somente com dados de desenvolvimento/validação
- [x] Comparação reproduzível Quant vs Quant+IA com replay de opiniões

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
