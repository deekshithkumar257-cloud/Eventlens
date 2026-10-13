def test_health_endpoint_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "EventLens API"
    assert body["database"] == "ok"
    assert body["version"]


def test_unknown_route_returns_consistent_error_shape(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_404"
    assert body["error"]["message"]
