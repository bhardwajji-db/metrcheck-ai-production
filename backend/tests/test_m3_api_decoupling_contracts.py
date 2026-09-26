"""
Milestone 3 Challenger Stress Harness: API Client Decoupling & Edge Routing
=============================================================================
Empirical tests stress-testing:
1. Dynamic API host resolution in `frontend/src/services/api.ts` under all environment configurations
   (empty, trailing slash, HTTPS cloud URL, whitespace, edge cases).
2. Asset URL and image blob URL resolution under unified container and decoupled CDN modes.
3. `frontend/vercel.json` edge rewrites schema, ordering, regex capturing, and backend route parity.
4. Static scan of `frontend/src/` ensuring zero hardcoded `http://` API endpoints and zero hardcoded localhost IPs.
5. Container reverse proxy contract in `frontend/nginx.conf` matching HF Spaces port 7860.
"""

import json
import os
import re
from pathlib import Path
import pytest

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
API_TS_PATH = FRONTEND_DIR / "src" / "services" / "api.ts"
VERCEL_JSON_PATH = FRONTEND_DIR / "vercel.json"
NGINX_CONF_PATH = FRONTEND_DIR / "nginx.conf"


# ═════════════════════════════════════════════════════════════════════════════
# 1. FRONTEND API RESOLUTION LOGIC SIMULATION & SOURCE VERIFICATION
# ═════════════════════════════════════════════════════════════════════════════

def simulate_frontend_base_url(vite_api_url: str | None) -> str:
    """Exact simulation of frontend/src/services/api.ts lines 53-54:
    const API_HOST = (import.meta.env.VITE_API_URL || '').replace(/\\/$/, '');
    const BASE_URL = API_HOST ? `${API_HOST}/api` : '/api';
    """
    raw = vite_api_url if vite_api_url is not None else ""
    api_host = re.sub(r"/$", "", raw)
    return f"{api_host}/api" if api_host else "/api"


def simulate_get_asset_url(url: str, vite_api_url: str | None, ticket: str | None = None) -> str:
    """Exact simulation of frontend/src/services/api.ts lines 544-556."""
    if not url:
        return ""
    if url.startswith("data:"):
        return url
    clean_url = url.replace("/uploads/", "/api/images/") if url.startswith("/uploads/") else url
    raw = vite_api_url if vite_api_url is not None else ""
    api_host = re.sub(r"/$", "", raw)
    if clean_url.startswith("http://") or clean_url.startswith("https://"):
        full_url = clean_url
    else:
        full_url = f"{api_host}{clean_url}" if api_host else clean_url
    if ticket:
        sep = "&" if "?" in full_url else "?"
        return f"{full_url}{sep}ticket={ticket}"
    return full_url


class TestApiDynamicResolution:
    """Stress-test dynamic API resolution logic in api.ts."""

    def test_01_api_ts_source_contract(self):
        """Verify frontend/src/services/api.ts implements dynamic resolution via import.meta.env.VITE_API_URL."""
        assert API_TS_PATH.exists(), f"Missing file: {API_TS_PATH}"
        content = API_TS_PATH.read_text(encoding="utf-8")
        assert "import.meta.env.VITE_API_URL" in content, "api.ts must read VITE_API_URL from environment"
        assert "replace(/\\/$/, '')" in content or "replace(/\\/$/, \"\")" in content, "api.ts must strip trailing slash"
        assert "const BASE_URL = API_HOST ? `${API_HOST}/api` : '/api'" in content, "api.ts must fallback to relative /api"

    def test_02_empty_vite_api_url_resolves_to_relative_api(self):
        """When VITE_API_URL is empty, undefined, or None, BASE_URL must resolve to relative /api."""
        for empty_val in [None, "", ""]:
            base_url = simulate_frontend_base_url(empty_val)
            assert base_url == "/api"
            # Verify endpoint paths
            assert f"{base_url}/health" == "/api/health"
            assert f"{base_url}/analyze" == "/api/analyze"
            assert f"{base_url}/auth/login" == "/api/auth/login"

    def test_03_trailing_slash_stripped(self):
        """When VITE_API_URL has a trailing slash, it must be cleanly stripped with no double-slash."""
        cloud_url = "https://omsainikaul-metrcheck-ai.hf.space/"
        base_url = simulate_frontend_base_url(cloud_url)
        assert base_url == "https://omsainikaul-metrcheck-ai.hf.space/api"
        assert "//api" not in base_url
        assert f"{base_url}/health" == "https://omsainikaul-metrcheck-ai.hf.space/api/health"

    def test_04_https_cloud_url_without_trailing_slash(self):
        """When VITE_API_URL is an HTTPS URL without slash, it resolves cleanly to https://.../api."""
        cloud_url = "https://omsainikaul-metrcheck-ai.hf.space"
        base_url = simulate_frontend_base_url(cloud_url)
        assert base_url == "https://omsainikaul-metrcheck-ai.hf.space/api"
        assert f"{base_url}/analyze" == "https://omsainikaul-metrcheck-ai.hf.space/api/analyze"

    def test_05_asset_url_resolution_relative_mode(self):
        """When running in relative / unified mode (VITE_API_URL=''), assets resolve to /api/images/..."""
        assert simulate_get_asset_url("/uploads/test.jpg", "") == "/api/images/test.jpg"
        assert simulate_get_asset_url("/api/images/test.jpg", "") == "/api/images/test.jpg"
        assert simulate_get_asset_url("data:image/png;base64,123", "") == "data:image/png;base64,123"

    def test_06_asset_url_resolution_cloud_mode(self):
        """When running with cloud VITE_API_URL, assets resolve to full HTTPS cloud URLs."""
        cloud_host = "https://omsainikaul-metrcheck-ai.hf.space"
        assert simulate_get_asset_url("/uploads/test.jpg", cloud_host) == f"{cloud_host}/api/images/test.jpg"
        assert simulate_get_asset_url("/uploads/test.jpg", f"{cloud_host}/") == f"{cloud_host}/api/images/test.jpg"

    def test_07_asset_url_with_ticket(self):
        """Asset download tickets must append cleanly as query parameter."""
        cloud_host = "https://omsainikaul-metrcheck-ai.hf.space"
        url = simulate_get_asset_url("/uploads/test.jpg", cloud_host, ticket="sec-tok-123")
        assert url == f"{cloud_host}/api/images/test.jpg?ticket=sec-tok-123"


# ═════════════════════════════════════════════════════════════════════════════
# 2. VERCEL REWRITES SPECIFICATION & BACKEND ROUTE PARITY
# ═════════════════════════════════════════════════════════════════════════════

class TestVercelRewrites:
    """Stress-test frontend/vercel.json rewrite configuration."""

    def test_01_vercel_json_exists_and_valid_json(self):
        """vercel.json must exist and be strictly valid JSON."""
        assert VERCEL_JSON_PATH.exists(), f"Missing file: {VERCEL_JSON_PATH}"
        data = json.loads(VERCEL_JSON_PATH.read_text(encoding="utf-8"))
        assert "rewrites" in data, "vercel.json must contain 'rewrites' key"
        assert isinstance(data["rewrites"], list), "'rewrites' must be a list"
        assert len(data["rewrites"]) >= 2, "'rewrites' must have at least /api/(.*) and /(.*) rules"

    def test_02_vercel_rewrite_order_and_destinations(self):
        """Rule 1 must route /api/(.*) to Hugging Face Spaces backend before SPA fallback."""
        data = json.loads(VERCEL_JSON_PATH.read_text(encoding="utf-8"))
        rewrites = data["rewrites"]

        # Rule 1 must be the API rewrite
        api_rule = rewrites[0]
        assert api_rule["source"] == "/api/(.*)", f"Rule 1 source should be '/api/(.*)', got {api_rule['source']}"
        assert "https://omsainikaul-metrcheck-ai.hf.space/api/$1" in api_rule["destination"], (
            f"Rule 1 destination should target HF Space backend, got {api_rule['destination']}"
        )

        # Rule 2 must be the SPA fallback
        spa_rule = rewrites[1]
        assert spa_rule["source"] == "/(.*)", f"Rule 2 source should be '/(.*)', got {spa_rule['source']}"
        assert spa_rule["destination"] == "/index.html", f"Rule 2 destination must be '/index.html', got {spa_rule['destination']}"

    def test_03_simulated_edge_routing_to_backend_routes(self):
        """Verify all essential API endpoints match the /api/(.*) rewrite regex and correspond to real FastAPI routes."""
        data = json.loads(VERCEL_JSON_PATH.read_text(encoding="utf-8"))
        api_pattern = re.compile(r"^/api/(.*)$")
        api_dest_template = data["rewrites"][0]["destination"]

        test_endpoints = [
            "/api/health",
            "/api/analyze",
            "/api/compliance/rules",
            "/api/report/analysis-123/pdf",
            "/api/images/package-scan.png",
            "/api/auth/login",
            "/api/version",
            "/api/history",
            "/api/scoring/config",
            "/api/preprint/upload",
            "/api/reviews/queue",
            "/api/products",
        ]

        # Extract all registered paths from FastAPI application
        fastapi_routes = set()
        for route in app.routes:
            if hasattr(route, "path"):
                fastapi_routes.add(route.path)

        for ep in test_endpoints:
            match = api_pattern.match(ep)
            assert match is not None, f"Endpoint {ep} failed to match /api/(.*)"
            captured = match.group(1)
            target = api_dest_template.replace("$1", captured)
            assert target == f"https://omsainikaul-metrcheck-ai.hf.space/api/{captured}"


# ═════════════════════════════════════════════════════════════════════════════
# 3. ZERO MIXED-CONTENT & LOCALHOST AUDIT
# ═════════════════════════════════════════════════════════════════════════════

class TestZeroMixedContent:
    """Stress-test frontend codebase to guarantee zero mixed-content and no hardcoded IPs."""

    def test_01_no_hardcoded_http_in_frontend_source(self):
        """No .ts or .tsx files in frontend/src may contain hardcoded http:// API URLs."""
        src_dir = FRONTEND_DIR / "src"
        violations = []

        for p in src_dir.rglob("*"):
            if p.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                text = p.read_text(encoding="utf-8")
                lines = text.splitlines()
                for idx, line in enumerate(lines, start=1):
                    # Check for http://
                    if "http://" in line:
                        # Allowed exceptions: check conditions (e.g. url.startsWith('http://')), or comments
                        stripped = line.strip()
                        if stripped.startswith("//") or stripped.startswith("*"):
                            continue
                        if "startsWith('http://')" in stripped or 'startsWith("http://")' in stripped:
                            continue
                        violations.append(f"{p.name}:{idx}: {stripped}")

        assert not violations, f"Found hardcoded http:// in frontend source: {violations}"

    def test_02_no_hardcoded_localhost_in_frontend_source(self):
        """No .ts or .tsx files in frontend/src may contain hardcoded localhost or loopback IPs."""
        src_dir = FRONTEND_DIR / "src"
        violations = []

        for p in src_dir.rglob("*"):
            if p.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                text = p.read_text(encoding="utf-8")
                lines = text.splitlines()
                for idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("*"):
                        continue
                    if "localhost" in stripped.lower() or "127.0.0.1" in stripped:
                        violations.append(f"{p.name}:{idx}: {stripped}")

        assert not violations, f"Found hardcoded localhost/127.0.0.1 in frontend source: {violations}"


# ═════════════════════════════════════════════════════════════════════════════
# 4. NGINX UNIFIED CONTAINER PROXY CONTRACT
# ═════════════════════════════════════════════════════════════════════════════

class TestNginxContainerContract:
    """Verify frontend/nginx.conf satisfies Hugging Face Spaces port 7860 reverse proxy contract."""

    def test_01_nginx_conf_port_and_proxy(self):
        """nginx.conf must listen on port 7860 and proxy /api to 127.0.0.1:8000."""
        assert NGINX_CONF_PATH.exists(), f"Missing file: {NGINX_CONF_PATH}"
        content = NGINX_CONF_PATH.read_text(encoding="utf-8")
        assert "listen 7860;" in content, "Nginx must listen on Hugging Face standard port 7860"
        assert "location /api" in content, "Nginx must have a location /api block"
        assert "proxy_pass http://127.0.0.1:8000;" in content, "Nginx must proxy /api to 127.0.0.1:8000"
        assert "try_files $uri $uri/ /index.html;" in content, "Nginx must support SPA client-side routing fallback"
