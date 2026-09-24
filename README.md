# MT5TITAN — Trade Intelligence

O projeto deixou de ser uma aplicação dependente do MetaTrader 5 e passou a ser uma aplicação web de inteligência para trading, com arquitetura de broker desacoplada.

## Estado atual

A aplicação funciona hoje com:

- dashboard web com watchlist e seleção de fonte de dados;
- API REST;
- market data desacoplado do broker (Demo + dados importados);
- análise quantitativa;
- feature pipeline;
- detector de regime;
- market score;
- Decision Engine;
- Risk Engine;
- agentes de IA e AI Committee;
- paper trading funcional e persistente em SQLite;
- research/backtest/walk-forward;
- replay, histórico de decisões e auditoria;
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


## Persistência local

Por padrão, a aplicação cria:

```text
data/mt5titan.db
```

O SQLite guarda o saldo paper, operações abertas/fechadas e o histórico das análises.
O diretório `data/` fica fora do Git.


## Market data

A aplicação possui uma camada independente da corretora:

- `demo`: série determinística para desenvolvimento e testes;
- `stored`: candles importados pelo usuário e persistidos no SQLite.

No dashboard, escolha a fonte, ativo e timeframe. Arquivos JSON podem conter diretamente
um array de candles ou um objeto com a propriedade `candles`.

Isso permite validar o motor Quant/Risk com dados externos sem depender de endpoints
privados da corretora.


## IA no web app

O modo Quant continua sendo o padrão. Para habilitar os agentes no dashboard:

```powershell
python -m pip install -e ".[dev,web,ai-openai]"
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="..."
mt5titan-web
```

Marque **IA** antes de analisar. O fluxo adiciona Technical Agent, News Agent,
Macro Agent e AI Committee. As opiniões são persistidas em replay, mas continuam
sem autoridade direta de execução.

Se as variáveis não estiverem configuradas, o backend recusa o modo IA com erro
explícito em vez de executar uma análise incompleta.


## Feedback loop de decisões

A versão 0.6.0 adiciona avaliação posterior das decisões.

Depois de uma análise, informe um preço futuro no dashboard e clique em **Avaliar última decisão**.
O sistema registra:

- WIN / LOSS / FLAT / HOLD;
- retorno direcional percentual;
- win rate agregado;
- desempenho por regime;
- acurácia direcional dos agentes Technical, News e Macro;
- acurácia direcional do AI Committee.

Essas métricas são observacionais. Elas ainda não alteram automaticamente os pesos dos agentes;
a calibração será uma etapa separada para evitar autoajuste com pouca amostra.


## Opportunity Scanner

A versão 0.7.0 adiciona um scanner em duas etapas:

```text
Watchlist
   ↓
Quant Scan
   ↓
Ranking preliminar
   ↓
Top 3 elegíveis
   ↓
Deep AI (opcional)
   ↓
Ranking final
```

O scanner calcula um `opportunity_score` de 0 a 100 usando market score,
força/confiança da decisão e confiança do regime. Ele também gera:

- direção BUY / SELL / HOLD;
- nível de risco;
- zona de entrada indicativa;
- preço de invalidação;
- horizonte compatível com o timeframe;
- identificação se o ranking veio de Quant ou Deep AI.

O scanner **não cria analysis_id** e não entra no histórico. Ao escolher uma
oportunidade e clicar em **Analisar**, a análise completa é executada e passa a
ser auditável/elegível para o feedback loop.

O botão **Popular demo** cria uma watchlist sintética para teste. Os preços gerados
não são cotações reais.


## Dados reais — Twelve Data

A versão 0.8.0 adiciona uma fonte oficial de market data via Twelve Data.

Configure localmente:

```powershell
$env:TWELVE_DATA_API_KEY="..."
$env:TWELVE_DATA_SCAN_LIMIT="6"
```

Depois escolha **Twelve Data (real)** no dashboard e use símbolos como:

```text
EURUSD
GBPUSD
USDJPY
XAUUSD
BTCUSD
AAPL
```

Símbolos Forex/cripto de seis letras são normalizados automaticamente para o formato
da API, como `EURUSD -> EUR/USD`.

O scanner limita por padrão a 6 símbolos Twelve Data por execução para reduzir o risco
de atingir o limite do plano gratuito. O limite pode ser alterado por
`TWELVE_DATA_SCAN_LIMIT`.

A chave nunca é enviada ao navegador nem armazenada no Git.


## Contexto gratuito de News/Macro

A versão 0.10.0 adiciona duas fontes externas independentes da OpenAI:

- **GDELT DOC 2.0** para headlines recentes. Não exige chave.
- **FRED** para contexto macro dos EUA. A chave é gratuita, mas opcional.

Séries macro consultadas atualmente:

```text
DFF       Effective Federal Funds Rate
DGS10     10-Year Treasury
VIXCLS    VIX
DTWEXBGS  Broad Dollar Index
```

Para habilitar FRED:

```powershell
$env:FRED_API_KEY="SUA_CHAVE"
```

No dashboard, **News/Macro** vem marcado por padrão. A análise não falha se GDELT
ou FRED estiverem indisponíveis; o contexto é marcado como indisponível e o Quant
continua funcionando.

As headlines são usadas como contexto/risk awareness, não como ordem automática
nem como prova de direção do mercado. O FRED também é contexto, não gatilho isolado.
