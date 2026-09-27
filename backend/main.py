import os

# Strict Linux container memory limits for 512MB RAM cloud tiers
os.environ["FLAGS_initial_cpu_memory_in_mb"] = "16"
os.environ["FLAGS_fraction_of_cpu_memory_to_use"] = "0.05"
os.environ["FLAGS_allocator_strategy"] = "naive_best_fit"
os.environ["FLAGS_eager_delete_tensor_gb"] = "0.0"
os.environ["FLAGS_fast_eager_deletion_mode"] = "1"
os.environ["FLAGS_memory_fraction_of_eager_deletion"] = "1.0"
os.environ["MALLOC_ARENA_MAX"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["PADDLE_NUM_THREADS"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database.db import init_db
from api import analyze, ocr, extract, compliance_routes, history, demo, health, report, enforcement, integrations, vision, evidence, scoring_routes, preprint_routes, version_routes, review_routes, images, products
from auth.routes import router as auth_router, admin_router, officer_access_router

from version import get_version_metadata
from database.db import get_security_audit_logs, verify_security_audit_chain
from auth.security import require_roles, ROLE_ADMIN
from fastapi import Request, Response, Depends, Query

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    settings.verify_test_isolation()
    settings.validate_production_secrets()
    try:
        await init_db()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Startup database initialization failed (service degraded): %s", exc)

    yield
    # Shutdown

app = FastAPI(title="MetrCheck AI API", version="2.4.0", lifespan=lifespan)

# ── Security Headers Middleware (Section 15) ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images.router, prefix="/api", tags=["Images"])
app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(ocr.router, prefix="/api", tags=["OCR"])
app.include_router(extract.router, prefix="/api", tags=["Extract"])
app.include_router(compliance_routes.router, prefix="/api", tags=["Compliance"])
app.include_router(evidence.router)
app.include_router(history.router, prefix="/api", tags=["History"])
app.include_router(demo.router, prefix="/api", tags=["Demo"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(report.router, prefix="/api", tags=["Report"])
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])
app.include_router(officer_access_router, prefix="/api", tags=["Officer Access"])
app.include_router(enforcement.router, prefix="/api", tags=["Enforcement"])
app.include_router(integrations.router, prefix="/api", tags=["Integrations & Metrology"])
app.include_router(vision.router)
app.include_router(scoring_routes.router)
app.include_router(preprint_routes.router)
app.include_router(version_routes.router)
app.include_router(review_routes.router)
app.include_router(products.router, prefix="/api")

@app.get("/api/version", tags=["System Version"])
def get_system_version():
    """Returns canonical system, OCR pipeline, rule engine, and integrity hashing versions."""
    return get_version_metadata()

@app.get("/api/admin/security-logs", tags=["Admin Governance"])
async def list_security_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str = Query(default=""),
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Retrieve immutable security audit logs with cryptographic hash blocks (Admin only)."""
    return await get_security_audit_logs(limit=limit, event_type=event_type)

@app.get("/api/admin/security-logs/verify-chain", tags=["Admin Governance"])
async def verify_audit_chain_endpoint(
    user: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Verifies the complete cryptographic SHA-256 hash chain of security audit logs (Admin only)."""
    return await verify_security_audit_chain()

@app.get("/")
def read_root():
    return {"message": "Welcome to MetrCheck AI API", "docs": "/docs", "version": "2.4.0"}
