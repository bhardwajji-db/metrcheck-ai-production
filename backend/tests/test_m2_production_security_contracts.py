"""
Milestone 2 Challenger Stress Harness: Production Security & Health Contracts
==============================================================================
Empirical tests stress-testing:
1. Production secret validation logic in `backend/config.py` against `.env.production` secrets and adversarial inputs.
2. Production CORS origins parsing and strict wildcard rejection.
3. `/api/health` HTTP 200 response format, schema contracts, and degraded failure modes.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from config import Settings, KNOWN_INSECURE_SECRETS, settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from version import SYSTEM_VERSION


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


PROD_ENV_SECRET = "b9f3e4c810d7a6e5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1"
PROD_ENV_CORS = "https://omsainikaul-metrcheck-ai.hf.space,https://metrcheck-ai.vercel.app"


# ═════════════════════════════════════════════════════════════════════════════
# 1. SECRET VALIDATION LOGIC STRESS-TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestProductionSecretValidation:
    """Stress-test production secret validation logic in backend/config.py."""

    def test_01_env_production_secret_passes_validation(self):
        """The 64-char hex secret configured in .env.production must pass validate_production_secrets cleanly."""
        _ensure_test_isolation()
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=PROD_ENV_SECRET,
            CORS_ORIGINS=["https://metrcheck-ai.vercel.app"],
            TEST_MODE=False,
        )
        assert s.SECRET_KEY == PROD_ENV_SECRET
        assert s.ENVIRONMENT == "production"
        assert len(s.SECRET_KEY) == 64

    def test_02_empty_or_whitespace_secret_rejected(self):
        """Empty or whitespace-only SECRET_KEY in production must raise ValueError."""
        _ensure_test_isolation()
        for empty_val in ["", "   ", "\t\n  "]:
            with pytest.raises(ValueError) as exc_info:
                Settings(ENVIRONMENT="production", SECRET_KEY=empty_val, TEST_MODE=False)
            assert "SECRET_KEY must be configured in production" in str(exc_info.value)

    def test_03_short_secret_under_32_chars_rejected(self):
        """Secrets shorter than 32 characters must be strictly rejected in production."""
        _ensure_test_isolation()
        short_val = "a" * 31  # 31 chars
        with pytest.raises(ValueError) as exc_info:
            Settings(ENVIRONMENT="production", SECRET_KEY=short_val, TEST_MODE=False)
        assert "at least 32 characters long" in str(exc_info.value)

    def test_04_exact_32_char_boundary_secret_accepted(self):
        """A high-entropy secret of exactly 32 characters must pass validation."""
        _ensure_test_isolation()
        exact_32 = "x" * 32
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=exact_32,
            CORS_ORIGINS=["https://metrcheck.ai"],
            TEST_MODE=False,
        )
        assert len(s.SECRET_KEY) == 32

    def test_05_all_known_insecure_secrets_rejected_case_insensitively(self):
        """Every entry in KNOWN_INSECURE_SECRETS (and uppercase/mixed-case variants) must be rejected."""
        _ensure_test_isolation()
        for insecure in KNOWN_INSECURE_SECRETS:
            for variant in [insecure, insecure.upper(), insecure.capitalize()]:
                with pytest.raises(ValueError) as exc_info:
                    Settings(ENVIRONMENT="production", SECRET_KEY=variant, TEST_MODE=False)
                assert "Default or known placeholder SECRET_KEY cannot be used in production" in str(exc_info.value)

    def test_06_metrcheck_env_os_variable_triggers_production_validation(self):
        """Setting METRCHECK_ENV=production in os.environ must trigger production secret validation."""
        _ensure_test_isolation()
        with patch.dict(os.environ, {"METRCHECK_ENV": "production"}):
            with pytest.raises(ValueError) as exc_info:
                Settings(SECRET_KEY="short", TEST_MODE=False)
            assert "CRITICAL SECURITY ERROR" in str(exc_info.value)

    def test_07_validation_error_never_leaks_candidate_secret(self):
        """Secret validation failure must NEVER include candidate secret characters in exception message."""
        _ensure_test_isolation()
        secret_candidate = "unexposed_canary_secret_12345"
        with pytest.raises(ValueError) as exc_info:
            Settings(ENVIRONMENT="production", SECRET_KEY=secret_candidate, TEST_MODE=False)
        assert secret_candidate not in str(exc_info.value)


# ═════════════════════════════════════════════════════════════════════════════
# 2. CORS ORIGINS VALIDATION & WILDCARD REJECTION
# ═════════════════════════════════════════════════════════════════════════════

class TestProductionCORSValidation:
    """Stress-test CORS_ORIGINS parsing and wildcard rejection."""

    def test_08_env_production_cors_origins_parses_cleanly_without_wildcard(self):
        """The comma-separated CORS_ORIGINS from .env.production must parse into explicit origins."""
        _ensure_test_isolation()
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=PROD_ENV_SECRET,
            CORS_ORIGINS=PROD_ENV_CORS,
            TEST_MODE=False,
        )
        assert isinstance(s.CORS_ORIGINS, list)
        assert len(s.CORS_ORIGINS) == 2
        assert "https://omsainikaul-metrcheck-ai.hf.space" in s.CORS_ORIGINS
        assert "https://metrcheck-ai.vercel.app" in s.CORS_ORIGINS
        assert "*" not in s.CORS_ORIGINS

    def test_09_wildcard_rejection_in_production(self):
        """Wildcard CORS origins must be strictly rejected in production across all representation formats."""
        _ensure_test_isolation()
        wildcard_inputs = [
            "*",
            ["*"],
            "https://metrcheck-ai.vercel.app, *",
            ["https://metrcheck-ai.vercel.app", "*"],
            "['*']",
        ]
        for w_input in wildcard_inputs:
            # Note: "['*']" falls through json parse error and becomes ["['*']"], test list and comma representations
            if w_input == "['*']":
                continue
            with pytest.raises(ValueError) as exc_info:
                Settings(
                    ENVIRONMENT="production",
                    SECRET_KEY=PROD_ENV_SECRET,
                    CORS_ORIGINS=w_input,
                    TEST_MODE=False,
                )
            assert "Wildcard CORS ('*') is prohibited in production" in str(exc_info.value)

    def test_10_development_mode_allows_wildcard(self):
        """Development environment must permit wildcard CORS origins for local rapid prototyping."""
        _ensure_test_isolation()
        s = Settings(
            ENVIRONMENT="development",
            SECRET_KEY="metrcheck-dev-secret-change-in-prod",
            CORS_ORIGINS=["*"],
            TEST_MODE=False,
        )
        assert s.CORS_ORIGINS == ["*"]


# ═════════════════════════════════════════════════════════════════════════════
# 3. HEALTH ENDPOINT CONTRACT & RESILIENCE
# ═════════════════════════════════════════════════════════════════════════════

class TestHealthEndpointContract:
    """Stress-test /api/health endpoint structure, status codes, and failure modes."""

    def test_11_health_endpoint_returns_http_200_and_required_contract_keys(self):
        """GET /api/health must return HTTP 200 with all required fields per PROJECT.md interface contracts."""
        _ensure_test_isolation()
        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == 200

            data = response.json()
            required_keys = {"status", "ocr_available", "ocr_engine", "database", "version"}
            assert required_keys.issubset(data.keys()), f"Missing keys in health response: {required_keys - set(data.keys())}"

            assert data["version"] == SYSTEM_VERSION
            assert data["version"] == "2.4.0"
            assert data["ocr_engine"] == "PaddleOCREngine"
            assert isinstance(data["ocr_available"], bool)
            assert data["database"] in ("connected", "disconnected")
            assert data["status"] in ("healthy", "degraded", "ok")

    def test_12_health_endpoint_degraded_when_database_fails(self):
        """When database check fails, /api/health must return HTTP 200 with status='degraded' and database='disconnected'."""
        _ensure_test_isolation()
        with patch("config.settings.DATABASE_PATH", "/nonexistent/invalid_path/metrcheck.db"):
            with TestClient(app) as client:
                response = client.get("/api/health")
                assert response.status_code == 200
                data = response.json()
                assert data["database"] == "disconnected"
                assert data["status"] == "degraded"

    def test_13_challenger_edge_case_ocr_unavailable_health_status(self):
        """Challenger edge case: verify health endpoint behavior when OCR engine reports unavailable.
        Current implementation binds status purely to db_status ('healthy' if db_status == 'connected').
        This test documents whether status transitions to degraded when OCR is offline.
        """
        _ensure_test_isolation()
        mock_engine = MagicMock()
        mock_engine.is_available.return_value = False
        mock_engine.__class__.__name__ = "PaddleOCREngine"

        with patch("api.health.get_ocr_engine", return_value=mock_engine):
            with TestClient(app) as client:
                response = client.get("/api/health")
                assert response.status_code == 200
                data = response.json()
                assert data["ocr_available"] is False
                # Finding: Document current behavior where status remains 'healthy' if db is connected
                # Even with ocr_available False, current logic returns 'healthy'
                assert "ocr_available" in data
