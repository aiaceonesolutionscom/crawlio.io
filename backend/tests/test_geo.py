async def test_list_countries(authed_client):
    await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})

    resp = await authed_client.get("/api/v1/geo/countries", params={"q": "pak"})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["items"]]
    assert any("Pakistan" in name for name in names)


async def test_list_cities_returns_items_not_a_coroutine_error(authed_client):
    """Regression test: list_cities used to `await` a synchronous
    geo_service.search_cities call, which crashed every request with
    TypeError: object list can't be used in 'await' expression."""
    await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})

    resp = await authed_client.get("/api/v1/geo/cities", params={"country": "PK", "q": "karachi"})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)


async def test_list_cities_falls_back_to_free_text_query(authed_client):
    await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})

    resp = await authed_client.get("/api/v1/geo/cities", params={"country": "PK", "q": "SomeTownNotInList"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "SomeTownNotInList"
