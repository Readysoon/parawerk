"""Nischenwerk: vom Foto der Wohnung zum Bauplan für den Baumarkt.

Aufbau nach MVC:
- models/       Domäne: Bauteilgraph, Sortiment, Bauteil-Engine, DXF
- services/     Anbindung externer KI-Dienste (Bild-KI, Claude) mit Demo-Ersatz
- views/        Jinja-Templates, Aufbereitung für die Anzeige, statische Dateien
- controllers/  FastAPI-Router
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .controllers import bauplan, entwuerfe, seiten
from .views import STATIC


def create_app() -> FastAPI:
    app = FastAPI(title="Nischenwerk", version="0.2.0",
                  description="Foto → Entwürfe → baubarer, stabiler Bauplan aus Baumarkt-Holz.")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(seiten.router)
    app.include_router(entwuerfe.router)
    app.include_router(bauplan.router)

    # Fehler immer als {"fehler": "..."} auf Deutsch, damit die Oberfläche sie direkt zeigen kann
    @app.exception_handler(StarletteHTTPException)
    async def http_fehler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"fehler": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def eingabe_fehler(_: Request, exc: RequestValidationError) -> JSONResponse:
        felder = ", ".join(".".join(str(p) for p in e["loc"][1:]) or "Anfrage" for e in exc.errors())
        return JSONResponse({"fehler": f"Ungültige Eingabe: {felder}."}, status_code=422)

    return app


app = create_app()
