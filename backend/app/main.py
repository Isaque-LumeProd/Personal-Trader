import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import get_settings
from .db import Base, SessionLocal, engine
from .migrate import upgrade_to_head
from .routers import (
    alerts,
    auth,
    dividends,
    events,
    imports,
    market,
    notifications,
    portfolio,
    rebalance,
    tax,
    transactions,
)
from .services.alerts_engine import alert_loop
from .services.market import get_market

logging.basicConfig(level=logging.INFO)
settings = get_settings()
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_migrate:
        upgrade_to_head()
    else:
        Base.metadata.create_all(engine)
    if settings.jwt_secret == "change-me-in-production":
        logging.getLogger(__name__).warning("JWT_SECRET padrão em uso: defina um segredo próprio em produção.")
    task = None
    if settings.alert_check_minutes > 0:
        task = asyncio.create_task(alert_loop(SessionLocal, get_market, settings))
    yield
    if task:
        task.cancel()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, transactions, dividends, events, imports, portfolio, market, rebalance, tax, alerts, notifications):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": settings.provider_name}


# Serve o frontend compilado (frontend/dist) quando existir: deploy em um único serviço.
if FRONTEND_DIST.is_dir():

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and FRONTEND_DIST in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
