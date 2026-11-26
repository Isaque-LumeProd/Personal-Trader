"""Universo padrão de FIIs e ETFs acompanhados pelo screener.

Os campos `demo_*` só são usados pelo provedor de demonstração (dados simulados).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogAsset:
    ticker: str
    name: str
    asset_type: str  # FII | ETF | ETF_RF
    segment: str
    demo_price: float
    demo_monthly_yield: float = 0.0  # rendimento mensal (FIIs) ou trimestral/3 (ETFs que distribuem)
    demo_pvp: float | None = None
    demo_vol: float = 0.18  # volatilidade anualizada
    demo_drift: float = 0.06  # retorno anual esperado (sem proventos)
    demo_dividend_every: int = 1  # meses entre distribuições (0 = não distribui)


CATALOG: list[CatalogAsset] = [
    # FIIs
    CatalogAsset("HGLG11", "CSHG Logística", "FII", "Logística", 158.0, 0.0085, 0.98, 0.14, 0.03),
    CatalogAsset("BTLG11", "BTG Pactual Logística", "FII", "Logística", 101.0, 0.0090, 0.95, 0.13, 0.02),
    CatalogAsset("XPLG11", "XP Log", "FII", "Logística", 98.0, 0.0088, 0.88, 0.15, 0.02),
    CatalogAsset("XPML11", "XP Malls", "FII", "Shoppings", 104.0, 0.0092, 0.93, 0.15, 0.03),
    CatalogAsset("VISC11", "Vinci Shopping Centers", "FII", "Shoppings", 106.0, 0.0086, 0.87, 0.15, 0.02),
    CatalogAsset("KNRI11", "Kinea Renda Imobiliária", "FII", "Híbrido", 154.0, 0.0072, 0.94, 0.12, 0.02),
    CatalogAsset("HGRU11", "CSHG Renda Urbana", "FII", "Renda Urbana", 126.0, 0.0084, 1.02, 0.13, 0.03),
    CatalogAsset("TRXF11", "TRX Real Estate", "FII", "Renda Urbana", 100.0, 0.0098, 0.96, 0.14, 0.02),
    CatalogAsset("PVBI11", "VBI Prime Properties", "FII", "Lajes Corporativas", 80.0, 0.0070, 0.78, 0.17, 0.02),
    CatalogAsset("MXRF11", "Maxi Renda", "FII", "Papel (CRI)", 9.6, 0.0105, 1.01, 0.10, 0.00),
    CatalogAsset("KNCR11", "Kinea Rendimentos Imobiliários", "FII", "Papel (CRI)", 105.0, 0.0110, 1.03, 0.07, 0.00),
    CatalogAsset("KNIP11", "Kinea Índices de Preços", "FII", "Papel (CRI)", 92.0, 0.0095, 0.97, 0.09, 0.00),
    CatalogAsset("CPTS11", "Capitânia Securities", "FII", "Papel (CRI)", 7.9, 0.0112, 0.89, 0.13, 0.00),
    CatalogAsset("VGIR11", "Valora RE", "FII", "Papel (CRI)", 9.5, 0.0118, 0.98, 0.11, 0.00),
    CatalogAsset("RBRF11", "RBR Alpha Multiestratégia", "FII", "Fundo de Fundos", 7.5, 0.0095, 0.85, 0.16, 0.01),
    # ETFs de renda variável
    CatalogAsset("BOVA11", "iShares Ibovespa", "ETF", "Ações Brasil", 150.0, 0.0, None, 0.20, 0.10, 0),
    CatalogAsset("SMAL11", "iShares Small Cap", "ETF", "Small Caps", 108.0, 0.0, None, 0.26, 0.08, 0),
    CatalogAsset("DIVO11", "It Now IDIV", "ETF", "Dividendos", 112.0, 0.0050, None, 0.17, 0.08, 3),
    CatalogAsset("IVVB11", "iShares S&P 500", "ETF", "Internacional", 380.0, 0.0, None, 0.18, 0.12, 0),
    CatalogAsset("NASD11", "Trend Nasdaq 100", "ETF", "Internacional", 16.0, 0.0, None, 0.24, 0.14, 0),
    CatalogAsset("GOLD11", "Trend Ouro", "ETF", "Commodities", 21.0, 0.0, None, 0.16, 0.08, 0),
    CatalogAsset("HASH11", "Hashdex Nasdaq Crypto", "ETF", "Cripto", 62.0, 0.0, None, 0.55, 0.15, 0),
    # ETFs de renda fixa (IR retido na fonte pelo administrador)
    CatalogAsset("IMAB11", "It Now IMA-B", "ETF_RF", "Renda Fixa (Inflação)", 96.0, 0.0, None, 0.06, 0.10, 0),
    CatalogAsset("B5P211", "It Now IMA-B5 P2", "ETF_RF", "Renda Fixa (Inflação)", 104.0, 0.0, None, 0.04, 0.11, 0),
]

CATALOG_BY_TICKER = {a.ticker: a for a in CATALOG}

ASSET_TYPES = ("FII", "ETF", "ETF_RF")


def guess_asset_type(ticker: str) -> str:
    asset = CATALOG_BY_TICKER.get(ticker)
    return asset.asset_type if asset else "FII"
