# Personal Trader

SaaS para investir e operar **FIIs e ETFs da B3**: carteira com preço médio, proventos, screener,
análise técnica com sinais de compra/venda, rebalanceamento por alocação-alvo e apuração de Imposto de Renda.

> Ferramenta de apoio à decisão. Não constitui recomendação de investimento.

## Funcionalidades

| Módulo | O que faz |
|---|---|
| **Carteira** | Patrimônio, valor investido, valorização, retorno total, evolução do patrimônio x capital investido, alocação por classe e segmento, posições com yield on cost |
| **Lançamentos** | Compras e vendas com taxas; preço médio pela regra da Receita (taxas entram no custo); bloqueia venda acima da posição |
| **Proventos** | Sincronização automática pela posição em cada *data com* + lançamento manual; histórico mensal e "a receber" |
| **Screener** | DY 12m, último provento, P/VP, liquidez, retornos, volatilidade, RSI e um *score* 0–100 relativo aos pares |
| **Análise técnica** | Preço com MM20/MM50 e Bandas de Bollinger, RSI(14), MACD(12,26,9); sinais combinados (tendência, cruzamento de médias, RSI, MACD, Bollinger) + sinais fundamentalistas (DY, P/VP) |
| **Rebalanceamento** | Alocação-alvo por ativo; modo "só comprar" (distribui o aporte sem vender) ou "comprar e vender" |
| **Imposto de Renda** | Apuração mensal (FII 20%, ETF 15%), compensação de prejuízo por categoria, IRRF 0,005%, DARF 6015 com vencimento, acúmulo abaixo de R$ 10; relatório anual (Bens e Direitos, proventos, vendas) |
| **Alertas** | Preço acima/abaixo, DY, RSI e sinais técnicos de compra/venda |
| **Multiusuário** | Cadastro/login com JWT; dados isolados por usuário |

## Arquitetura

```
backend/   FastAPI + SQLAlchemy (SQLite por padrão, Postgres em produção)
  app/providers/   brapi.dev (dados reais) e demo (dados simulados, sem rede)
  app/services/    regras de negócio puras: carteira, IR, indicadores, rebalanceamento, métricas
  app/routers/     API REST em /api/*
  tests/           pytest (serviços + fluxo completo da API)
frontend/  React + Vite + TypeScript + Recharts
```

## Dados de mercado

- **brapi.dev** (recomendado): crie um token em https://brapi.dev e defina `BRAPI_TOKEN`.
  FIIs exigem token. O plano gratuito limita o histórico a 3 meses — o app tenta `HISTORY_RANGE`
  e cai para `3mo` automaticamente (médias de 200 dias e retorno de 12 meses ficam indisponíveis nesse caso).
- **Modo demo**: sem token, o app usa séries simuladas determinísticas para todo o catálogo,
  ideal para desenvolvimento e testes. A interface avisa quando está em modo demo.
- O P/VP só aparece quando a fonte o informa (a brapi não fornece P/VP de FIIs em todos os planos).

Respostas são guardadas em cache em memória por `CACHE_TTL_SECONDS` (padrão 15 min).

## Rodando localmente

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # opcional: preencha BRAPI_TOKEN e JWT_SECRET
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (em outro terminal):

```bash
cd frontend
npm install
npm run dev
```

Acesse http://localhost:5173 e crie uma conta. A documentação interativa da API fica em http://localhost:8000/docs.

Testes e verificação de tipos:

```bash
cd backend && .venv/bin/python -m pytest
```

```bash
cd frontend && npm run typecheck
```

## Deploy

Um único container serve a API e o frontend compilado:

```bash
BRAPI_TOKEN=seu-token JWT_SECRET=um-segredo-longo docker compose up --build
```

Em produção: defina um `JWT_SECRET` forte, use Postgres em `DATABASE_URL`
(ex.: `postgresql+psycopg://...`, instalando `psycopg[binary]`) e ajuste `CORS_ORIGINS`.

## Regras de IR implementadas (pessoa física, swing trade)

- **FIIs**: 20% sobre o lucro na venda; prejuízos só compensam lucros de FIIs. Rendimentos mensais são isentos
  (respeitadas as condições de enquadramento do fundo).
- **ETFs de renda variável**: 15% sobre o lucro; **não** há isenção de R$ 20 mil.
- **ETFs de renda fixa**: IR retido na fonte pelo administrador — ficam fora do DARF.
- IRRF de 0,005% sobre o valor de venda é deduzido; DARF abaixo de R$ 10 acumula para o mês seguinte.
- Alíquotas são configuráveis (`TAX_RATE_FII`, `TAX_RATE_ETF`) caso a legislação mude.
- **Limitações**: day trade não é separado; feriados não são considerados no vencimento do DARF.

## Próximos passos sugeridos

- Importação de notas de corretagem / extrato da B3 (CSV)
- Verificação periódica de alertas em background com envio por e-mail/Telegram
- Separação de day trade e eventos corporativos (desdobramentos, grupamentos, amortizações no custo)
- Migrações com Alembic e cobrança de assinatura (Stripe / Mercado Pago)
- Integração de ordens com corretoras que ofereçam API
