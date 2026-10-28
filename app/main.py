"""FastAPI application: routers, CSRF protection, security headers."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import observability
from app.admin.routes import router as admin_router
from app.auth.routes import router as auth_router
from app.billing.routes import router as billing_router
from app.config import get_settings
from app.family.routes import router as family_router
from app.portal import router as portal_router

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {"/api/billing/webhook"}

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https://swisssciencetutors.ch; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://checkout.stripe.com https://billing.stripe.com"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(self), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Content-Security-Policy", CSP)
        if get_settings().cookies_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-submit check for authenticated state-changing requests."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if (
            request.method in UNSAFE_METHODS
            and request.url.path.startswith("/api/")
            and request.url.path not in CSRF_EXEMPT_PATHS
            and request.cookies.get(settings.session_cookie_name)
        ):
            cookie = request.cookies.get(settings.csrf_cookie_name)
            header = request.headers.get("x-csrf-token")
            if not cookie or not header or cookie != header:
                return JSONResponse({"detail": "csrf_failed"}, status_code=403)
        return await call_next(request)


def create_app() -> FastAPI:
    observability.configure()
    settings = get_settings()
    app = FastAPI(
        title="SST Virtual Tutor API",
        version="0.1.0",
        docs_url="/api/docs" if settings.app_env in ("dev", "test", "staging") else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    )
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(auth_router)
    app.include_router(billing_router)
    app.include_router(family_router)
    app.include_router(admin_router)
    app.include_router(portal_router)

    @app.get("/api/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    # Serve the built front end if present (single-container deployments and local
    # demos). In production Caddy serves web/dist directly and proxies /api here.
    dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
