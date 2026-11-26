# Personal Trader

SaaS para investir e operar **FIIs e ETFs da B3**: carteira com preço médio, proventos, screener,
análise técnica com sinais de compra/venda, rebalanceamento por alocação-alvo e apuração de Imposto de Renda.

> Ferramenta de apoio à decisão. Não constitui recomendação de investimento.

## Funcionalidades

| Módulo | O que faz |
|---|---|
| **Carteira** | Patrimônio, valor investido, valorização, retorno total, evolução do patrimônio x capital investido, alocação por classe e segmento, posições com yield on cost |
| **Lançamentos** | Compras e vendas com taxas; preço médio pela regra da Receita (taxas entram no custo); bloqueia venda acima da posição |
| **Importar da B3** | Lê os extratos de Negociação (compras/vendas) e Movimentação (rendimentos, dividendos, JCP, amortizações) da Área do Investidor, em .xlsx ou .csv, ou uma planilha no modelo próprio; pré-visualização, detecção de duplicados e confirmação |
| **Eventos corporativos** | Desdobramentos e grupamentos ajustam a quantidade sem mudar o custo; amortizações reduzem o preço médio |
| **Proventos** | Sincronização automática pela posição em cada *data com* + lançamento manual; histórico mensal e "a receber" |
| **Screener** | DY 12m, último provento, P/VP, liquidez, retornos, volatilidade, RSI e um *score* 0–100 relativo aos pares |
| **Análise técnica** | Preço com MM20/MM50 e Bandas de Bollinger, RSI(14), MACD(12,26,9); sinais combinados (tendência, cruzamento de médias, RSI, MACD, Bollinger) + sinais fundamentalistas (DY, P/VP) |
| **Rebalanceamento** | Alocação-alvo por ativo; modo "só comprar" (distribui o aporte sem vender) ou "comprar e vender" |
| **Imposto de Renda** | Apuração mensal (FII 20%, ETF 15%, day trade 20%), compensação de prejuízo por categoria, IRRF (0,005% e 1% no day trade), DARF 6015 com vencimento, acúmulo abaixo de R$ 10; relatório anual (Bens e Direitos, proventos, vendas) |
| **Alertas e notificações** | Preço acima/abaixo, DY, RSI e sinais técnicos; verificação automática em segundo plano durante o pregão; aviso no app, por Telegram e por e-mail (no máximo uma vez por dia por alerta) |
| **Multiusuário** | Cadastro/login com JWT; dados isolados por usuário |

## Arquitetura

```
backend/   FastAPI + SQLAlchemy + Alembic (SQLite por padrão, Postgres em produção)
  migrations/      migrações do banco (aplicadas automaticamente ao iniciar)
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

### Netlify (frontend) + Render (API e banco)

O Netlify só hospeda o frontend; a API Python roda no Render. O Netlify repassa `/api/*` para a API,
então o navegador fala apenas com o domínio do Netlify (sem CORS).

1. **Render**: em *New → Blueprint*, escolha este repositório. O `render.yaml` cria a API e um Postgres.
   Preencha `BRAPI_TOKEN` (e, se quiser, `TELEGRAM_BOT_TOKEN`). Anote a URL da API, ex.:
   `https://personal-trader-api.onrender.com` — teste em `/api/health`.
2. **Netlify**: em *Add new site → Import an existing project*, escolha este repositório (o `netlify.toml`
   já define pasta, build e publicação). Em *Site configuration → Environment variables*, crie
   `API_URL` com a URL da API e faça o deploy.
3. No Render, defina `APP_URL` com o endereço do site no Netlify (usado nos e-mails de alerta).

No plano gratuito do Render a API "dorme" após um período sem acesso: o primeiro acesso demora
e a verificação automática de alertas não roda enquanto ela dorme. Para alertas confiáveis, use um
plano pago (ou mantenha a verificação manual). Confira também os limites do Postgres gratuito do Render.

### Docker (tudo em um serviço)

Um único container serve a API e o frontend compilado:

```bash
BRAPI_TOKEN=seu-token JWT_SECRET=um-segredo-longo docker compose up --build
```

O `docker-compose.yml` sobe a aplicação com **Postgres 16**. As migrações rodam sozinhas ao iniciar
(`AUTO_MIGRATE=true`); para rodar manualmente: `cd backend && .venv/bin/alembic upgrade head`.
Bancos criados pela versão 0.1 (antes das migrações) são reconhecidos e atualizados sem perda de dados.

Em produção: defina um `JWT_SECRET` forte e ajuste `CORS_ORIGINS` e `APP_URL`.

### Notificações

- **Telegram**: crie um bot com o @BotFather e defina `TELEGRAM_BOT_TOKEN`. Cada usuário informa
  seu *chat id* em Configurações (depois de mandar uma mensagem ao bot).
- **E-mail**: defina `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM`.
- `ALERT_CHECK_MINUTES` (padrão 15; 0 desativa) e `ALERT_MARKET_HOURS_ONLY` (dias úteis, 10h–18h30 de Brasília).
- A verificação roda dentro do processo da API: com vários *workers*/réplicas, deixe-a ligada em só um
  (ou mova para um job agendado).

## Regras de IR implementadas (pessoa física, swing trade)

- **FIIs**: 20% sobre o lucro na venda; prejuízos só compensam lucros de FIIs. Rendimentos mensais são isentos
  (respeitadas as condições de enquadramento do fundo).
- **ETFs de renda variável**: 15% sobre o lucro; **não** há isenção de R$ 20 mil.
- **ETFs de renda fixa**: IR retido na fonte pelo administrador — ficam fora do DARF.
- IRRF de 0,005% sobre o valor de venda é deduzido; DARF abaixo de R$ 10 acumula para o mês seguinte.
- Alíquotas são configuráveis (`TAX_RATE_FII`, `TAX_RATE_ETF`) caso a legislação mude.
- **Day trade**: compra e venda do mesmo ativo no mesmo dia formam day trade na quantidade casada, ao preço
  médio das compras do dia; 20% de alíquota; em ETFs, prejuízo de day trade só compensa lucro de day trade.
- **Limitações**: feriados não são considerados no vencimento do DARF; frações de grupamento ficam
  fracionadas (o leilão de sobras deve ser lançado como venda).

## Próximos passos sugeridos

- Cobrança de assinatura (Stripe ou Mercado Pago) e planos
- Leitura de notas de corretagem em PDF (para trazer as taxas)
- Recuperação de senha por e-mail
- Integração de ordens com corretoras que ofereçam API
