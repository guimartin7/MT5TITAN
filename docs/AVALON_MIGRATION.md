# Migração para Avalon / aplicação web

## Decisão arquitetural

O núcleo Quant/AI/Risk foi preservado e a dependência direta do MT5 foi removida do caminho principal da aplicação.

A nova camada `mt5titan.brokers` define a fronteira entre inteligência e execução.

## Modos atuais

### Paper
Funcional e habilitado.

### Avalon
Adapter criado, porém execução real desabilitada até existir documentação oficial de API/SDK ou autorização explícita de integração.

Não usamos endpoints privados descobertos no browser, scraping autenticado ou automação de cliques.

## Web API

- `GET /api/health`
- `GET /api/brokers`
- `GET /api/demo/candles`
- `POST /api/analyze`
- `GET /api/paper`
- `POST /api/paper/order`
- `POST /api/paper/settle`

## Próximos adapters possíveis

O mesmo contrato pode receber futuramente uma fonte oficial de mercado/corretora sem alterar Decision Engine, Risk Engine ou AI Committee.
