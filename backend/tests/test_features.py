import io
from datetime import timedelta

from openpyxl import Workbook

from app.services.importer import normalize_ticker, parse_number


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_number_and_ticker_parsing():
    assert parse_number("R$ 1.234,56") == 1234.56
    assert parse_number("1,234.56") == 1234.56
    assert parse_number("9,6") == 9.6
    assert parse_number(10) == 10
    assert normalize_ticker("HGLG11F") == "HGLG11"
    assert normalize_ticker("MXRF11 - MAXI RENDA FDO INV IMOB - FII") == "MXRF11"


def test_import_b3_trades_xlsx(client, auth, today):
    d1 = (today - timedelta(days=40)).strftime("%d/%m/%Y")
    d2 = (today - timedelta(days=10)).strftime("%d/%m/%Y")
    content = _xlsx([
        ["Data do Negócio", "Tipo de Movimentação", "Mercado", "Prazo/Vencimento", "Instituição", "Código de Negociação", "Quantidade", "Preço", "Valor"],
        [d1, "Compra", "Mercado à Vista", "-", "CORRETORA", "HGLG11", 10, 150.5, 1505],
        [d1, "Compra", "Mercado Fracionário", "-", "CORRETORA", "MXRF11F", 30, "9,80", "294,00"],
        [d1, "Compra", "Mercado Fracionário", "-", "CORRETORA", "MXRF11F", 30, "9,80", "294,00"],
        [d2, "Venda", "Mercado à Vista", "-", "CORRETORA", "HGLG11", 4, 160, 640],
        [d2, "Compra", "Mercado à Vista", "-", "CORRETORA", "PETR4", 100, 40, 4000],
    ])
    files = {"file": ("negociacao.xlsx", content, "application/octet-stream")}
    r = client.post("/api/import/preview", files=files, headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["format"] == "b3_negociacao"
    assert data["summary"] == {"ok": 4, "ignored": 1}
    ok = [row for row in data["rows"] if row["status"] == "ok"]
    assert {row["ticker"] for row in ok} == {"HGLG11", "MXRF11"}

    body = {"trades": [{k: row[k] for k in ("ticker", "asset_type", "side", "date", "quantity", "price", "fees")} for row in ok]}
    r = client.post("/api/import/commit", json=body, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["trades"] == 4

    # reimportar marca tudo como duplicado (inclusive as duas linhas idênticas)
    again = client.post("/api/import/preview", files=files, headers=auth).json()
    assert again["summary"] == {"duplicate": 4, "ignored": 1}

    positions = {p["ticker"]: p for p in client.get("/api/portfolio/summary", headers=auth).json()["positions"]}
    assert positions["HGLG11"]["quantity"] == 6
    assert positions["MXRF11"]["quantity"] == 60


def test_import_b3_movements_csv(client, auth, today):
    client.post("/api/transactions", json={"ticker": "HGLG11", "side": "BUY", "date": (today - timedelta(days=120)).isoformat(), "quantity": 10, "price": 150}, headers=auth)
    pay = (today - timedelta(days=5)).strftime("%d/%m/%Y")
    csv_text = (
        "Entrada/Saída;Data;Movimentação;Produto;Instituição;Quantidade;Preço unitário;Valor da Operação\n"
        f"Credito;{pay};Rendimento;HGLG11 - CSHG LOGISTICA FII;CORRETORA;10;1,10;11,00\n"
        f"Debito;{pay};Transferência - Liquidação;HGLG11 - CSHG LOGISTICA FII;CORRETORA;10;150,00;1500,00\n"
    )
    r = client.post("/api/import/preview", files={"file": ("mov.csv", csv_text.encode("latin-1"), "text/csv")}, headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["format"] == "b3_movimentacao"
    row = next(x for x in data["rows"] if x["status"] == "ok")
    assert row["dividend_kind"] == "RENDIMENTO" and row["amount"] == 11
    r = client.post("/api/import/commit", json={"dividends": [{k: row[k] for k in ("ticker", "dividend_kind", "date", "quantity", "price", "amount")}]}, headers=auth)
    assert r.status_code == 200


def test_import_rejects_unknown_header(client, auth):
    r = client.post("/api/import/preview", files={"file": ("x.csv", b"a;b\n1;2\n", "text/csv")}, headers=auth)
    assert r.status_code == 400


def test_import_commit_rolls_back_invalid_history(client, auth, today):
    body = {"trades": [{"ticker": "HGLG11", "asset_type": "FII", "side": "SELL", "date": today.isoformat(), "quantity": 5, "price": 150}]}
    assert client.post("/api/import/commit", json=body, headers=auth).status_code == 400
    assert client.get("/api/transactions", headers=auth).json() == []


def test_split_event_endpoint(client, auth, today):
    client.post("/api/transactions", json={"ticker": "MXRF11", "side": "BUY", "date": (today - timedelta(days=30)).isoformat(), "quantity": 10, "price": 100}, headers=auth)
    r = client.post("/api/events", json={"ticker": "MXRF11", "kind": "SPLIT", "date": (today - timedelta(days=10)).isoformat(), "factor": 10}, headers=auth)
    assert r.status_code == 201, r.text
    pos = client.get("/api/portfolio/summary", headers=auth).json()["positions"][0]
    assert pos["quantity"] == 100 and abs(pos["avg_price"] - 10) < 1e-9
    # grupamento que deixaria uma venda posterior sem cotas é recusado
    client.post("/api/transactions", json={"ticker": "MXRF11", "side": "SELL", "date": (today - timedelta(days=2)).isoformat(), "quantity": 80, "price": 10}, headers=auth)
    r = client.post("/api/events", json={"ticker": "MXRF11", "kind": "REVERSE_SPLIT", "date": (today - timedelta(days=5)).isoformat(), "factor": 10}, headers=auth)
    assert r.status_code == 400
    assert len(client.get("/api/events", headers=auth).json()) == 1


def test_alert_creates_notification_once_per_cooldown(client, auth):
    client.post("/api/alerts", json={"ticker": "MXRF11", "kind": "PRICE_ABOVE", "threshold": 1}, headers=auth)
    first = client.post("/api/alerts/check", headers=auth).json()["results"][0]
    assert first["triggered"] and first["notified"]
    second = client.post("/api/alerts/check", headers=auth).json()["results"][0]
    assert second["triggered"] and not second["notified"]
    notes = client.get("/api/notifications", headers=auth).json()
    assert notes["unread"] == 1 and "MXRF11" in notes["items"][0]["message"]
    assert client.post("/api/notifications/read-all", headers=auth).status_code == 204
    assert client.get("/api/notifications", headers=auth).json()["unread"] == 0


def test_user_settings(client, auth):
    s = client.get("/api/settings", headers=auth).json()
    assert s["channels_available"] == {"telegram": False, "email": False}
    r = client.put("/api/settings", json={"telegram_chat_id": "123456", "notify_email": True}, headers=auth)
    assert r.status_code == 200 and r.json()["telegram_chat_id"] == "123456"
    assert client.put("/api/settings", json={"telegram_chat_id": "abc"}, headers=auth).status_code == 422
    # sem canais configurados no servidor, o teste cai só na notificação interna
    assert client.post("/api/settings/test-notification", headers=auth).json()["channels"] == ["app"]


def test_market_hours():
    from datetime import datetime, timezone

    from app.services.alerts_engine import market_open

    assert market_open(datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc))  # quarta, 12h em Brasília
    assert not market_open(datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc))  # sábado
    assert not market_open(datetime(2026, 11, 25, 23, 0, tzinfo=timezone.utc))  # 20h em Brasília


def test_delivery_uses_configured_channels(client, auth, monkeypatch):
    from app.services import alerts_engine

    sent = []

    async def fake_telegram(settings, chat_id, text):
        sent.append((chat_id, text))
        return True

    monkeypatch.setattr(alerts_engine, "send_telegram", fake_telegram)
    client.put("/api/settings", json={"telegram_chat_id": "42"}, headers=auth)
    assert client.post("/api/settings/test-notification", headers=auth).json()["channels"] == ["app", "telegram"]
    assert sent and sent[0][0] == "42"


def test_notification_timestamps_are_utc(client, auth):
    client.post("/api/settings/test-notification", headers=auth)
    created = client.get("/api/notifications", headers=auth).json()["items"][0]["created_at"]
    assert created.endswith("Z") or created.endswith("+00:00")
