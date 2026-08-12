from app.services import geo_service


class TestNearbyCities:
    def test_returns_nearest_cities_for_pakistan(self):
        results = geo_service.nearby_cities("PK", "Islamabad", n=2)
        assert 1 <= len(results) <= 2
        names = {c["name"] for c in results}
        assert "Islamabad" not in names

    def test_results_sorted_nearest_first(self):
        results = geo_service.nearby_cities("PK", "Islamabad", n=5)
        origin = next(c for c in geo_service.CITIES["PK"] if c["name"] == "Islamabad")
        distances = [
            geo_service._haversine_km(origin["lat"], origin["lon"], c["lat"], c["lon"])
            for c in results
        ]
        assert distances == sorted(distances)

    def test_unknown_origin_city_returns_empty(self):
        assert geo_service.nearby_cities("PK", "NotARealCityAtAll", n=2) == []

    def test_country_with_at_most_one_city_returns_empty(self):
        single_city_countries = [
            code for code, cities in geo_service.CITIES.items() if len(cities) <= 1
        ]
        assert single_city_countries, "expected at least one single-city country in test data"
        code = single_city_countries[0]
        city_name = geo_service.CITIES[code][0]["name"]
        assert geo_service.nearby_cities(code, city_name, n=2) == []

    def test_excludes_null_island_placeholder(self):
        # search_cities()'s free-text pass-through uses (0.0, 0.0) — must never
        # be treated as a real coordinate for distance math.
        results = geo_service.nearby_cities("PK", "Islamabad", n=200)
        assert all(not (c["lat"] == 0.0 and c["lon"] == 0.0) for c in results)


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
