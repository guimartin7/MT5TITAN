# OpenAI provider — execução controlada

O MT5TITAN usa um adapter isolado para a OpenAI API.

## Regras de segurança

- `OPENAI_API_KEY` existe somente no ambiente local.
- A chave nunca entra em prompts, `AgentContext`, replay ou logs.
- `OPENAI_MODEL` é configurável por ambiente.
- Os agentes recebem somente um contexto estruturado e auditável.
- A saída do modelo precisa respeitar JSON Schema estrito.
- Nenhum provider possui acesso ao MetaTrader 5 ou a `order_send`.
- O resultado dos agentes vira apenas uma opinião para o `AICommittee`.
- O Committee também não executa ordens.
- A execução continua atrás de Risk Engine, policy, reconciliation e preflight.

## Instalação

```powershell
python -m pip install -e ".[dev,ai-openai]"
```

## Variáveis locais

Crie um `.env` local ou configure as variáveis no PowerShell. O projeto não lê
automaticamente arquivos `.env`; isso evita introduzir dependência ou comportamento
implícito. Exemplo:

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="..."
```

Nunca envie a chave para o GitHub.

## Fluxo experimental

```text
Closed bars
   ↓
Features / Regime / Market score
   ↓
Quant signals
   ↓
AgentContext
   ↓
OpenAIProvider
   ↓
Technical / News / Macro opinions
   ↓
OpinionReplayStore
   ↓
AICommittee
   ↓
Quant vs Quant+AI benchmark
```

As respostas podem ser gravadas em replay para que o benchmark posterior não faça
novas chamadas de API e continue reproduzível.

## Importante

A camada de IA é experimental. Um resultado `PROMOTE_AI_EXPERIMENT` significa
somente que o experimento pode avançar para outra etapa de pesquisa. Não autoriza
paper, Demo ou operação real.
