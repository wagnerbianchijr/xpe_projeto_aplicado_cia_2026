"""Fábrica do app FastAPI para o dashboard IIoT da Serra Clara."""
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import SupportsFetch
from queries import (
    failed_sensors,
    failing_sensors,
    kpis,
    sensor_meta,
    sensor_status,
    timeseries,
    violations,
)

_BASE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE / "templates"))


class _DbError:
    """Flag mutável repassada para a renderização de um template."""

    def __init__(self) -> None:
        self.failed = False


def safe(flag: "_DbError", fn: Callable[[], Any], default: Any) -> Any:
    """Executa uma consulta; em caso de falha, define a flag de erro e retorna o default."""
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

    @app.get("/api/alerts", response_class=HTMLResponse)
    def api_alerts(request: Request):
        flag = _DbError()
        alerts = safe(flag, lambda: failing_sensors(db), [])
        return _TEMPLATES.TemplateResponse(
            request, "partials/alerts.html", ctx(request, alerts=alerts, db_error=flag.failed)
        )

    def _line_id(value: str | None) -> int | None:
        if value in (None, "", "all"):
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @app.get("/operational", response_class=HTMLResponse)
    def operational(request: Request, line_id: str | None = None):
        return _TEMPLATES.TemplateResponse(
            request,
            "operational.html",
            ctx(request, active="operational", line_id=line_id or "all"),
        )

    @app.get("/api/operational", response_class=HTMLResponse)
    def api_operational(request: Request, line_id: str | None = None):
        flag = _DbError()
        lid = _line_id(line_id)
        rows = safe(flag, lambda: sensor_status(db, lid), [])
        failed = safe(flag, lambda: failed_sensors(db, lid), [])
        return _TEMPLATES.TemplateResponse(
            request,
            "partials/operational_table.html",
            ctx(request, rows=rows, failed=failed, db_error=flag.failed),
        )

    @app.get("/performance", response_class=HTMLResponse)
    def performance(request: Request):
        return _TEMPLATES.TemplateResponse(
            request, "performance.html", ctx(request, active="performance")
        )

    @app.get("/api/timeseries")
    def api_timeseries(sensor_id: int, window: int = 3600):
        meta = sensor_meta(db, sensor_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="sensor não encontrado")
        points = timeseries(db, sensor_id, meta.metric, window)
        return JSONResponse({
            "metric": meta.metric,
            "unit": meta.unit,
            "limits": {"min": meta.min_limit, "max": meta.max_limit},
            "points": [
                {"time": p.time.isoformat(), "value": p.value} for p in points
            ],
        })

    @app.get("/sensor/{sensor_id}", response_class=HTMLResponse)
    def sensor_detail(request: Request, sensor_id: int):
        flag = _DbError()
        meta = safe(flag, lambda: sensor_meta(db, sensor_id), None)
        if flag.failed:
            return _TEMPLATES.TemplateResponse(
                request,
                "sensor_detail.html",
                ctx(request, meta=None, violations=[], db_error=True),
            )
        if meta is None:
            raise HTTPException(status_code=404, detail="sensor não encontrado")
        recent = safe(flag, lambda: violations(db, meta.line_id, 7 * 24 * 3600), [])
        sensor_violations = [v for v in recent if v.sensor_id == sensor_id]
        return _TEMPLATES.TemplateResponse(
            request,
            "sensor_detail.html",
            ctx(request, meta=meta, violations=sensor_violations, db_error=flag.failed),
        )

    return app
