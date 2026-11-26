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

    # Tributação (swing trade). Alíquotas configuráveis caso a legislação mude.
    tax_rate_fii: float = 0.20
    tax_rate_etf: float = 0.15
    irrf_rate: float = 0.00005  # "dedo-duro" 0,005% sobre o valor de venda
    darf_minimum: float = 10.0

    @property
    def provider_name(self) -> str:
        if self.market_data_provider == "auto":
            return "brapi" if self.brapi_token else "demo"
        return self.market_data_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
