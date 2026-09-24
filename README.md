# MT5TITAN — Trade Intelligence

O projeto deixou de ser uma aplicação dependente do MetaTrader 5 e passou a ser uma aplicação web de inteligência para trading, com arquitetura de broker desacoplada.

## Estado atual

A aplicação funciona hoje com:

- dashboard web;
- API REST;
- análise quantitativa;
- feature pipeline;
- detector de regime;
- market score;
- Decision Engine;
- Risk Engine;
- agentes de IA e AI Committee;
- paper trading funcional;
- research/backtest/walk-forward;
- replay e auditoria;
- adapter de broker desacoplado.

## Avalon Broker

Existe um boundary `AvalonBrokerAdapter`, porém a execução real permanece desabilitada enquanto não houver uma API/SDK oficial documentada ou integração fornecida/autorizada pela corretora.

O projeto não depende de endpoints privados do navegador e não automatiza cliques na plataforma.

## Rodando a aplicação

```powershell
python -m pip install -e ".[dev,web]"
mt5titan-web
```

Abra:

```text
http://127.0.0.1:8000
```

No dashboard, use **Analisar demo** para executar o pipeline completo e abrir operações no paper broker.

## Arquitetura

```text
Market Data / Replay
        ↓
Feature Pipeline
        ↓
Regime + Market Score
        ↓
Quant Strategies
        ↓
AI Committee
        ↓
Decision Engine
        ↓
Risk Engine
        ↓
Broker Adapter
       / \
 Paper    Avalon
  ✅       aguardando API oficial
```

## Segurança

- IA nunca executa ordens diretamente.
- Risk Engine continua soberano.
- Paper trading é o único modo de execução habilitado por padrão.
- Credenciais ficam fora do repositório.
- Integrações de corretora ficam isoladas em `mt5titan.brokers`.
