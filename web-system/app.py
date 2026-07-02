"""FastAPI app factory for the Serra Clara IIoT dashboard."""
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import SupportsFetch
from queries import (
    failed_sensors,
    kpis,
    sensor_meta,
    sensor_status,
    timeseries,
    violations,
)

_BASE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE / "templates"))


class _DbError:
    """Mutable flag threaded into a template render."""

    def __init__(self) -> None:
        self.failed = False


def safe(flag: "_DbError", fn: Callable[[], Any], default: Any) -> Any:
    """Run a query; on any failure set the error flag and return default."""
    try:
        return fn()
    except Exception:
        flag.failed = True
        return default


def create_app(db: SupportsFetch, refresh_seconds: int = 5) -> FastAPI:
    app = FastAPI(title="Serra Clara Bebidas — IIoT Dashboard")
    app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")

    def ctx(request: Request, **extra: Any) -> dict:
        base = {"request": request, "refresh_seconds": refresh_seconds}
        base.update(extra)
        return base

    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request):
        return _TEMPLATES.TemplateResponse(
            request, "overview.html", ctx(request, active="overview")
        )

    @app.get("/api/kpis", response_class=HTMLResponse)
    def api_kpis(request: Request):
        flag = _DbError()
        data = safe(flag, lambda: kpis(db), None)
        return _TEMPLATES.TemplateResponse(
            request, "partials/kpis.html", ctx(request, kpi=data, db_error=flag.failed)
        )

    return app
