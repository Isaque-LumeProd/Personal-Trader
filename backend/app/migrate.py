"""Aplica as migrações Alembic ao iniciar a aplicação."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .db import engine

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def upgrade_to_head() -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "users" in tables and "alembic_version" not in tables:
            # banco criado pela versão 0.1 (create_all, antes das migrações)
            log.info("Banco sem controle de versão: marcando como revisão 0001")
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")
