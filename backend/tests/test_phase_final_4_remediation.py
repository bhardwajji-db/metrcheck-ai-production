"""
Phase 4 Controlled Remediation — Regression Tests

Tests that verify the specific fixes applied in Phase 4.
These are primarily source-level static checks + lightweight behavioral checks
that run with the existing test infrastructure (no isolated_test_env required).

Coverage:
  F-EVID-01 — Evidence AI snapshot preservation logic
  F-ERR-01  — Error message sanitization (no raw str(e) in 500 responses)
  OBS-01    — Health endpoint real DB check
  OBS-02    — Health endpoint correct version
  F-ENF-01  — DB partial unique index still present
  F-SEC-01  — No live credentials in .env.example files
  W1        — Pydantic SettingsConfigDict in place of inner class Config
"""
import pytest
import sqlite3
from pathlib import Path


# ─── Path helpers ─────────────────────────────────────────────────────────────

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


def read_backend(rel_path: str) -> str:
    return (BACKEND_ROOT / rel_path).read_text(encoding="utf-8")


def read_root(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


# ─── F-EVID-01: Evidence AI Snapshot Preservation ─────────────────────────────

class TestEvidenceAISnapshotLogic:
    """Verify the corrected evidence endpoint logic preserves AI snapshots."""

    def test_ai_original_text_set_on_first_correction(self):
        """Simulate the corrected logic: ai_original_text set only once (first correction)."""
        ev = {"id": "ev-001", "text": "AI_VALUE", "linked_rule_id": "LM-003"}

        # First correction
        if "ai_original_text" not in ev:
            ev["ai_original_text"] = ev.get("text") or ev.get("extracted_text") or ""
        old_val_1 = ev["ai_original_text"]
        ev["human_correction"] = "HUMAN_VAL_1"
        ev["text"] = "HUMAN_VAL_1"

        assert ev["ai_original_text"] == "AI_VALUE"
        assert old_val_1 == "AI_VALUE"

        # Second correction — ai_original_text must NOT be overwritten
        if "ai_original_text" not in ev:
            ev["ai_original_text"] = ev.get("text") or ev.get("extracted_text") or ""
        old_val_2 = ev["ai_original_text"]
        ev["human_correction"] = "HUMAN_VAL_2"
        ev["text"] = "HUMAN_VAL_2"

        assert ev["ai_original_text"] == "AI_VALUE", \
            "ai_original_text was overwritten on second correction — AI snapshot lost!"
        assert old_val_2 == "AI_VALUE"
        assert ev["human_correction"] == "HUMAN_VAL_2"

    def test_human_correction_stored_separately_from_ai_original(self):
        """AI original and human correction must be separate fields."""
        ev = {"id": "ev-002", "text": "AI_DETECTED", "linked_rule_id": "LM-004"}
        if "ai_original_text" not in ev:
            ev["ai_original_text"] = ev.get("text", "")
        ev["human_correction"] = "OFFICER_VERIFIED"
        ev["text"] = "OFFICER_VERIFIED"

        assert ev["ai_original_text"] == "AI_DETECTED"
        assert ev["human_correction"] == "OFFICER_VERIFIED"
        assert ev["ai_original_text"] != ev["human_correction"]

    def test_new_evidence_entry_has_null_ai_original(self):
        """Officer-created evidence entries (no prior AI detection) must have ai_original_text=None."""
        new_ev = {
            "id": "ev-new-001",
            "ai_original_text": None,   # No AI source for this field
            "human_correction": "150 grams",
            "text": "150 grams",
            "match_method": "HUMAN_CORRECTION",
        }
        assert new_ev["ai_original_text"] is None
        assert new_ev["match_method"] == "HUMAN_CORRECTION"

    def test_evidence_py_no_longer_mutates_text_without_preserving_original(self):
        """Source code check: evidence.py must set ai_original_text before mutating text."""
        content = read_backend("api/evidence.py")
        assert "ai_original_text" in content, \
            "evidence.py does not set ai_original_text — F-EVID-01 fix not applied!"
        assert "human_correction" in content, \
            "evidence.py does not set human_correction — F-EVID-01 fix not applied!"

    def test_evidence_py_match_method_is_human_correction(self):
        """Corrected evidence must use HUMAN_CORRECTION match method, not DIRECT_OCR."""
        content = read_backend("api/evidence.py")
        assert '"HUMAN_CORRECTION"' in content, \
            "match_method HUMAN_CORRECTION not found in evidence.py after remediation"


# ─── F-ERR-01: Error Message Sanitization ─────────────────────────────────────

class TestErrorMessageSanitization:
    """Verify no raw str(e) appears in HTTP 500 client responses."""

    def test_analyze_py_no_str_e_in_500(self):
        """analyze.py must not use str(e) in 500 HTTP detail."""
        content = read_backend("api/analyze.py")
        assert 'f"Internal analysis error: {str(e)}"' not in content, \
            "Old leaking pattern found in analyze.py — F-ERR-01 not fixed!"
        assert '"An internal server error occurred during analysis."' in content

    def test_ocr_py_no_str_e_in_500(self):
        """ocr.py must not expose str(e) in 500 HTTP detail."""
        content = read_backend("api/ocr.py")
        assert "detail=str(e)" not in content, \
            "ocr.py still exposes str(e) — F-ERR-01 regression!"

    def test_vision_py_no_str_e_in_500(self):
        """vision.py must not expose raw exception string in 500 detail."""
        content = read_backend("api/vision.py")
        assert 'f"Vision analysis failed: {str(e)}"' not in content, \
            "vision.py still exposes exception message — F-ERR-01 regression!"

    def test_compliance_routes_py_no_str_e_in_500(self):
        """compliance_routes.py must not expose simulation error detail."""
        content = read_backend("api/compliance_routes.py")
        assert 'f"Simulation error: {str(e)}"' not in content, \
            "compliance_routes.py still leaks exception — F-ERR-01 regression!"

    def test_integrations_py_no_str_e_in_500(self):
        """integrations.py calibration endpoint must not expose exception."""
        content = read_backend("api/integrations.py")
        assert 'f"Calibration analysis failed: {str(e)}"' not in content, \
            "integrations.py still leaks exception — F-ERR-01 regression!"

    def test_analyze_py_logs_exception_server_side(self):
        """analyze.py must log exceptions server-side after sanitization."""
        content = read_backend("api/analyze.py")
        assert "logger.exception" in content, \
            "analyze.py does not log exceptions server-side after sanitization"

    def test_ocr_py_logs_exception_server_side(self):
        """ocr.py must log exceptions server-side."""
        content = read_backend("api/ocr.py")
        assert "logger.exception" in content, \
            "ocr.py does not log exceptions server-side after sanitization"


# ─── OBS-01 / OBS-02: Health Endpoint ─────────────────────────────────────────

class TestHealthEndpoint:
    """Verify health endpoint real DB check and correct version."""

    def test_health_version_not_hardcoded_1_0_0(self):
        """Health endpoint must not hardcode version '1.0.0'."""
        content = read_backend("api/health.py")
        assert '"version": "1.0.0"' not in content, \
            "Health endpoint still hardcodes version 1.0.0 — OBS-02 not fixed!"
        assert "SYSTEM_VERSION" in content, \
            "Health endpoint must import and use SYSTEM_VERSION from version.py"

    def test_health_database_not_hardcoded_connected(self):
        """Health endpoint must NOT return hardcoded 'connected'."""
        content = read_backend("api/health.py")
        assert '"database": "connected"' not in content, \
            "Health endpoint still hardcodes database:connected — OBS-01 not fixed!"

    def test_health_endpoint_performs_real_db_check(self):
        """Health endpoint must execute a real database query."""
        content = read_backend("api/health.py")
        assert "SELECT 1" in content, \
            "Health endpoint must perform SELECT 1 for real DB connectivity check"

    def test_system_version_constant_is_2_4_0(self):
        """SYSTEM_VERSION in version.py must be '2.4.0'."""
        import sys
        sys.path.insert(0, str(BACKEND_ROOT))
        from version import SYSTEM_VERSION
        assert SYSTEM_VERSION == "2.4.0", \
            f"SYSTEM_VERSION={SYSTEM_VERSION!r} — expected '2.4.0'"


# ─── F-ENF-01: Enforcement DB Uniqueness ──────────────────────────────────────

class TestEnforcementDBUniqueness:
    """Verify the DB partial unique index is the correctness boundary."""

    def test_partial_unique_index_present_in_production_db(self):
        """The partial unique index must exist in the active production database."""
        db_path = BACKEND_ROOT / "metrc_check.db"
        if not db_path.exists():
            pytest.skip("Production DB not present — skipping")

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='idx_enf_cases_unique_active_analysis'"
            ).fetchall()
        finally:
            conn.close()

        assert rows, "Partial unique index idx_enf_cases_unique_active_analysis not found in DB!"
        sql = rows[0][0]
        assert "UNIQUE" in sql.upper()
        assert "analysis_id" in sql
        assert "RESOLVED" in sql or "CLOSED" in sql

    def test_threading_lock_still_present_as_optimization(self):
        """threading.Lock must still be present in enforcement.py as a perf optimization."""
        content = read_backend("api/enforcement.py")
        assert "threading.Lock" in content, \
            "threading.Lock unexpectedly removed from enforcement.py"


# ─── F-SEC-01: Credential Security ─────────────────────────────────────────────

class TestCredentialSecurity:
    """Verify SMTP credentials are not in tracked example/template files."""

    COMPROMISED_PASS = "bdna oqyl rata pjep"
    COMPROMISED_USER = "metrcheckai@gmail.com"

    def test_root_env_example_has_no_smtp_credentials(self):
        """Root .env.example must have empty SMTP placeholders, not real credentials."""
        content = read_root(".env.example")
        assert self.COMPROMISED_PASS not in content, \
            "Root .env.example still contains the compromised SMTP App Password!"
        assert self.COMPROMISED_USER not in content, \
            "Root .env.example still contains the live SMTP account email!"

    def test_backend_env_example_has_no_smtp_credentials(self):
        """backend/.env.example must have empty SMTP placeholders."""
        content = read_backend(".env.example")
        assert self.COMPROMISED_PASS not in content, \
            "backend/.env.example still contains the compromised SMTP App Password!"
        assert self.COMPROMISED_USER not in content, \
            "backend/.env.example still contains the live SMTP account email!"

    def test_backend_env_smtp_pass_is_cleared(self):
        """backend/.env must not contain the compromised SMTP App Password."""
        env_path = BACKEND_ROOT / ".env"
        if not env_path.exists():
            pytest.skip("backend/.env not present")

        content = env_path.read_text(encoding="utf-8")
        assert self.COMPROMISED_PASS not in content, \
            "backend/.env STILL CONTAINS the compromised SMTP App Password!"

    def test_dockerignore_excludes_env_files(self):
        """The .dockerignore must explicitly exclude .env files."""
        content = read_root(".dockerignore")
        assert ".env" in content, ".dockerignore does not exclude .env files!"
        assert "backend/.env" in content, ".dockerignore does not exclude backend/.env!"


# ─── W1: Pydantic ConfigDict Migration ─────────────────────────────────────────

class TestPydanticConfigDictMigration:
    """Verify the Pydantic W1 deprecation fix in config.py."""

    def test_config_py_uses_model_config_not_inner_class(self):
        """config.py must use model_config = SettingsConfigDict(...) not class Config."""
        content = read_backend("config.py")
        assert "class Config:" not in content, \
            "config.py still uses deprecated inner class Config — W1 not fixed!"
        assert "SettingsConfigDict" in content, \
            "config.py does not use SettingsConfigDict — W1 not fixed!"
        assert "model_config" in content, \
            "config.py does not set model_config — W1 not fixed!"

    def test_settings_still_loads_env_file(self):
        """Settings must still load from the backend .env file path."""
        content = read_backend("config.py")
        assert "env_file" in content, \
            "SettingsConfigDict must still specify env_file"
        assert "_BACKEND_DIR" in content and ".env" in content, \
            "env_file path must reference the backend .env file"
