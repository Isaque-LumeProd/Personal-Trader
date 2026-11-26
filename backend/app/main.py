import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import get_settings
from .db import Base, engine
from .routers import alerts, auth, dividends, market, portfolio, rebalance, tax, transactions

logging.basicConfig(level=logging.INFO)
settings = get_settings()
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.jwt_secret == "change-me-in-production":
        logging.getLogger(__name__).warning("JWT_SECRET padrão em uso: defina um segredo próprio em produção.")
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, transactions, dividends, portfolio, market, rebalance, tax, alerts):
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
