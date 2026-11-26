from datetime import timedelta


def test_requires_auth(client):
    assert client.get("/api/portfolio/summary").status_code == 401


def test_login(client, auth):
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "senha-forte-123"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "errada"}).status_code == 401


def test_full_flow(client, auth, today):
    buy_date = (today - timedelta(days=200)).isoformat()
    for body in (
        {"ticker": "hglg11", "side": "BUY", "date": buy_date, "quantity": 10, "price": 150, "fees": 1},
        {"ticker": "BOVA11", "side": "BUY", "date": buy_date, "quantity": 5, "price": 140},
        {"ticker": "HGLG11", "side": "SELL", "date": (today - timedelta(days=30)).isoformat(), "quantity": 2, "price": 170},
    ):
        r = client.post("/api/transactions", json=body, headers=auth)
        assert r.status_code == 201, r.text

    # venda maior que a posição é rejeitada
    r = client.post("/api/transactions", json={"ticker": "HGLG11", "side": "SELL", "date": today.isoformat(), "quantity": 100, "price": 170}, headers=auth)
    assert r.status_code == 400

    r = client.post("/api/dividends/sync", headers=auth)
    assert r.status_code == 200 and r.json()["created"] > 0
    assert client.post("/api/dividends/sync", headers=auth).json()["created"] == 0  # idempotente

    s = client.get("/api/portfolio/summary", headers=auth).json()
    assert {p["ticker"] for p in s["positions"]} == {"HGLG11", "BOVA11"}
    hglg = next(p for p in s["positions"] if p["ticker"] == "HGLG11")
    assert hglg["quantity"] == 8
    assert s["totals"]["dividends_total"] > 0
    assert len(s["dividends_monthly"]) == 12

    evo = client.get("/api/portfolio/evolution?days=90", headers=auth).json()
    assert len(evo["points"]) > 30

    tax = client.get("/api/tax/monthly", headers=auth).json()
    assert tax["months"][0]["categories"][0]["category"] == "FII"
    assert tax["months"][0]["categories"][0]["result"] > 0

    annual = client.get(f"/api/tax/annual?year={today.year}", headers=auth).json()
    assert annual["assets"]

    r = client.put("/api/rebalance/targets", json=[{"ticker": "HGLG11", "target_pct": 60}, {"ticker": "MXRF11", "target_pct": 40}], headers=auth)
    assert r.status_code == 200
    reb = client.post("/api/rebalance", json={"contribution": 2000, "mode": "aporte"}, headers=auth).json()
    assert reb["cash_left"] < 200
    assert any(r["ticker"] == "MXRF11" and r["trade_quantity"] > 0 for r in reb["rows"])
    assert client.put("/api/rebalance/targets", json=[{"ticker": "HGLG11", "target_pct": 50}], headers=auth).status_code == 400


def test_market_and_screener(client, auth):
    a = client.get("/api/market/analysis/HGLG11?days=120", headers=auth).json()
    assert len(a["series"]) == 120
    assert a["metrics"]["dy_12m"] > 5
    assert a["technical"]["recommendation"]
    assert a["fundamentals"]

    s = client.get("/api/screener?asset_type=FII&sort=dy_12m&order=desc", headers=auth).json()
    dys = [r["dy_12m"] for r in s["results"]]
    assert dys == sorted(dys, reverse=True)
    assert all(r["asset_type"] == "FII" for r in s["results"])
    assert all(0 <= r["score"] <= 100 for r in s["results"])


def test_alerts(client, auth):
    r = client.post("/api/alerts", json={"ticker": "MXRF11", "kind": "PRICE_ABOVE", "threshold": 1}, headers=auth)
    assert r.status_code == 201
    assert client.post("/api/alerts", json={"ticker": "MXRF11", "kind": "PRICE_BELOW"}, headers=auth).status_code == 400
    res = client.post("/api/alerts/check", headers=auth).json()["results"]
    assert res[0]["triggered"] is True


def test_users_are_isolated(client, auth, today):
    client.post("/api/transactions", json={"ticker": "KNRI11", "side": "BUY", "date": today.isoformat(), "quantity": 1, "price": 150}, headers=auth)
    other = client.post("/api/auth/register", json={"name": "Bia", "email": "bia@example.com", "password": "outra-senha-123"}).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get("/api/transactions", headers=headers).json() == []
    tx_id = client.get("/api/transactions", headers=auth).json()[0]["id"]
    assert client.delete(f"/api/transactions/{tx_id}", headers=headers).status_code == 404
