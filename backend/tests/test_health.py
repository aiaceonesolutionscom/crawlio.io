async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert set(body["circuit_breakers"]) == {
        "google_maps",
        "bing_maps",
        "bizdata",
        "directory",
    }
    assert "sources" in body
    assert "unhealthy_sources" in body