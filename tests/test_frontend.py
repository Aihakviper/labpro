from fastapi.testclient import TestClient


def test_frontend_login_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Librarian Pro" in response.text
    assert 'id="login-form"' in response.text
    assert 'src="/static/js/app.js"' in response.text


def test_frontend_static_assets_are_served(client: TestClient) -> None:
    css_response = client.get("/static/css/app.css")
    js_response = client.get("/static/js/app.js")
    api_js_response = client.get("/static/js/api.js")

    assert css_response.status_code == 200
    assert "--lp-primary" in css_response.text
    assert js_response.status_code == 200
    assert "renderDashboard" in js_response.text
    assert api_js_response.status_code == 200
    assert "apiRequest" in api_js_response.text
