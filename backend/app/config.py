from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Personal Trader"
    database_url: str = "sqlite:///./personal_trader.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173"]

    # Dados de mercado
    market_data_provider: str = "auto"  # auto | brapi | demo
    brapi_token: str | None = None
    brapi_base_url: str = "https://brapi.dev/api"
    history_range: str = "1y"
    cache_ttl_seconds: int = 900

    # Alertas e notificações
    alert_check_minutes: int = 15  # 0 desativa a verificação em segundo plano
    alert_market_hours_only: bool = True  # só verifica em dias úteis, das 10h às 18h30 (Brasília)
    alert_cooldown_hours: int = 20  # intervalo mínimo entre dois avisos do mesmo alerta
    telegram_bot_token: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    app_url: str = "http://localhost:5173"

    # Banco
    auto_migrate: bool = True  # aplica migrações Alembic ao iniciar

    # Tributação (swing trade). Alíquotas configuráveis caso a legislação mude.
    tax_rate_fii: float = 0.20
    tax_rate_etf: float = 0.15
    tax_rate_daytrade: float = 0.20
    irrf_rate: float = 0.00005  # "dedo-duro" 0,005% sobre o valor de venda (operações comuns)
    irrf_daytrade_rate: float = 0.01  # 1% sobre o resultado positivo de day trade
    darf_minimum: float = 10.0

    @property
    def provider_name(self) -> str:
        if self.market_data_provider == "auto":
            return "brapi" if self.brapi_token else "demo"
        return self.market_data_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
