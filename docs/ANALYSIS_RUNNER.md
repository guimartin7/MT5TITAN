# Analysis Runner

O comando `mt5titan-analyze` executa o fluxo completo de análise sem gateway de
execução e sem chamada a `order_send`.

## Instalação

Sem IA:

```powershell
python -m pip install -e ".[dev,mt5]"
```

Com OpenAI:

```powershell
python -m pip install -e ".[dev,mt5,ai-openai]"
```

## Quant-only

```powershell
mt5titan-analyze --symbol WINV26 --timeframe M5 --bars 250
```

## Quant + OpenAI

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="..."
mt5titan-analyze --symbol WINV26 --timeframe M5 --bars 250 --ai
```

## Saída

O relatório JSON contém:

- snapshot Bid/Ask;
- saúde do feed;
- features;
- regime;
- market score;
- sinais Quant;
- sinal do AI Committee, quando habilitado;
- decisão final;
- resultado do Risk Engine;
- indicação explícita de que execução está desabilitada.

Replays de IA são gravados separadamente para permitir benchmarks posteriores sem
novas chamadas ao provider.

## Garantia operacional

Este runner não importa nem instancia o execution gateway e não contém nenhuma
chamada a `order_send`.
