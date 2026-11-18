"""
Comprehensive Frontend Dashboard Test Suite (Phase 4).
Tests Flask template rendering, static asset availability, content negotiation,
and structural element integrity across all 8 dashboard sections.
"""
import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


# =============================================================================
# 1. Dashboard Template Route
# =============================================================================
def test_dashboard_route_renders_html(client):
    """Verify GET /dashboard returns 200 OK and renders the HTML dashboard."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    html = resp.get_data(as_text=True)

    # Verify key dashboard layout landmarks
    assert "Urban Microclimate & Heat-Risk Intelligence System" in html
    assert "app-container" in html
    assert "sidebar" in html
    assert "main-wrapper" in html
    assert "topbar" in html


# =============================================================================
# 2. Content Negotiation on Root Route (/)
# =============================================================================
def test_root_content_negotiation_browser_vs_api(client):
    """
    Verify GET / renders HTML when browser Accept: text/html is sent,
    and returns JSON metadata when programmatic Accept: */* or application/json is sent.
    """
    # 1. Browser navigation request
    browser_resp = client.get("/", headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    assert browser_resp.status_code == 200
    assert "text/html" in browser_resp.content_type
    assert "Urban Microclimate & Heat-Risk Intelligence System" in browser_resp.get_data(as_text=True)

    # 2. Programmatic API client request (Accept: */*)
    api_resp = client.get("/", headers={"Accept": "*/*"})
    assert api_resp.status_code == 200
    assert "application/json" in api_resp.content_type
    json_data = api_resp.get_json()
    assert "service" in json_data
    assert json_data["database"] == "Apache HBase 2.6.7 (REST)"


# =============================================================================
# 3. Static Assets Accessibility
# =============================================================================
def test_static_assets_served_correctly(client):
    """Verify that CSS and JS modules are served with 200 OK."""
    assets = [
        ("/static/css/dashboard.css", "css"),
        ("/static/js/api.js", "javascript"),
        ("/static/js/charts.js", "javascript"),
        ("/static/js/map.js", "javascript"),
        ("/static/js/alerts.js", "javascript"),
        ("/static/js/simulator.js", "javascript"),
        ("/static/js/app.js", "javascript"),
    ]

    for path, expected_substr in assets:
        resp = client.get(path)
        assert resp.status_code == 200, f"Failed to serve {path}"
        assert expected_substr in resp.content_type, f"MIME mismatch for {path}: {resp.content_type}"


# =============================================================================
# 4. Verification of All 8 Dashboard Sections
# =============================================================================
def test_all_eight_dashboard_sections_present(client):
    """Verify all 8 specified functional sections exist in the HTML DOM."""
    resp = client.get("/dashboard")
    html = resp.get_data(as_text=True)

    required_sections = [
        "section-overview",
        "section-live",
        "section-analytics",
        "section-air-quality",
        "section-heat-risk",
        "section-alerts",
        "section-stations",
        "section-system"
    ]

    for section_id in required_sections:
        assert f'id="{section_id}"' in html, f"Missing section: {section_id}"


# =============================================================================
# 5. Core Widgets & Governance Verification
# =============================================================================
def test_core_dashboard_widgets_and_badges(client):
    """Verify presence of map container, chart canvases, modals, and SIMULATED badge."""
    resp = client.get("/dashboard")
    html = resp.get_data(as_text=True)

    # Leaflet map container
    assert 'id="station-map"' in html

    # Chart canvases
    assert 'id="overview-trend-chart"' in html
    assert 'id="live-metrics-chart"' in html
    assert 'id="historical-trend-chart"' in html
    assert 'id="air-quality-bar-chart"' in html
    assert 'id="heat-risk-comparison-chart"' in html

    # Modals
    assert 'id="stationDetailModal"' in html
    assert 'id="acknowledgeModal"' in html

    # Clear SIMULATED provenance disclosure
    assert "SIMULATED DATA" in html
    assert "SIMULATED STATIONS" in html
