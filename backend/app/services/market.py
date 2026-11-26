import asyncio
import logging
import time

from ..config import Settings, get_settings
from ..providers.base import AssetData, MarketDataError, MarketDataProvider
from ..providers.brapi import BrapiProvider
from ..providers.demo import DemoProvider

log = logging.getLogger(__name__)


class MarketService:
    """Busca dados de mercado com cache em memória (TTL)."""

    def __init__(self, provider: MarketDataProvider, ttl_seconds: int = 900, max_concurrency: int = 5):
        self.provider = provider
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, AssetData]] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def provider_name(self) -> str:
        return self.provider.name

    async def get(self, ticker: str) -> AssetData:
        ticker = ticker.upper()
        cached = self._cache.get(ticker)
        if cached and time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        async with self._semaphore:
            data = await self.provider.fetch(ticker)
        self._cache[ticker] = (time.monotonic(), data)
        return data

    async def get_many(self, tickers: list[str]) -> tuple[dict[str, AssetData], dict[str, str]]:
        """Retorna (dados por ticker, erros por ticker) sem falhar o lote inteiro."""
        unique = sorted({t.upper() for t in tickers})
        results = await asyncio.gather(*(self.get(t) for t in unique), return_exceptions=True)
        data, errors = {}, {}
        for ticker, res in zip(unique, results):
            if isinstance(res, AssetData):
                data[ticker] = res
            else:
                msg = res.message if isinstance(res, MarketDataError) else str(res)
                log.warning("market data error for %s: %s", ticker, msg)
                errors[ticker] = msg
        return data, errors


def build_market_service(settings: Settings | None = None) -> MarketService:
    settings = settings or get_settings()
    if settings.provider_name == "brapi":
        provider: MarketDataProvider = BrapiProvider(
            settings.brapi_token, settings.brapi_base_url, settings.history_range
        )
    else:
        provider = DemoProvider()
    return MarketService(provider, settings.cache_ttl_seconds)


_service: MarketService | None = None


def get_market() -> MarketService:
    global _service
    if _service is None:
        _service = build_market_service()
    return _service
