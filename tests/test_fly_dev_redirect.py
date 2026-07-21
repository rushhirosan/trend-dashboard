"""*.fly.dev → PUBLIC_BASE_URL への 301 リダイレクト"""

import pytest

from app import _is_fly_dev_host, create_app


@pytest.mark.parametrize(
    "host,expected",
    [
        ("trends-dashboard.fly.dev", True),
        ("Trends-Dashboard.FLY.DEV", True),
        ("trends-dashboard.fly.dev:443", True),
        ("trends-dashboard.com", False),
        ("localhost", False),
        ("", False),
    ],
)
def test_is_fly_dev_host(host, expected):
    assert _is_fly_dev_host(host) is expected


@pytest.fixture(scope="module")
def app_client():
    app, _scheduler = create_app()
    app.config["TESTING"] = True
    app.config["PUBLIC_BASE_URL"] = "https://trends-dashboard.com"
    with app.test_client() as client:
        yield client


def test_fly_dev_root_redirects(app_client):
    res = app_client.get("/", headers={"Host": "trends-dashboard.fly.dev"})
    assert res.status_code == 301
    assert res.headers["Location"] == "https://trends-dashboard.com/"


def test_fly_dev_path_and_query_redirects(app_client):
    res = app_client.get(
        "/us?foo=1",
        headers={"Host": "trends-dashboard.fly.dev"},
    )
    assert res.status_code == 301
    assert res.headers["Location"] == "https://trends-dashboard.com/us?foo=1"


def test_custom_domain_does_not_redirect(app_client):
    res = app_client.get("/", headers={"Host": "trends-dashboard.com"})
    assert res.status_code == 200


def test_healthz_not_redirected(app_client):
    res = app_client.get("/healthz", headers={"Host": "trends-dashboard.fly.dev"})
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
