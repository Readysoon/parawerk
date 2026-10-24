"""Parawerk: vom Foto der Wohnung zum Bauplan für den Baumarkt.

Aufbau nach MVC:
- models/       Domäne: Bauteilgraph, Sortiment, Bauteil-Engine, DXF
- services/     Anbindung externer KI-Dienste (Bild-KI, Claude) mit Demo-Ersatz
- views/        Jinja-Templates, Aufbereitung für die Anzeige, statische Dateien
- controllers/  FastAPI-Router
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .controllers import api_v1, bauplan, entwuerfe, kontingent, seiten
from .i18n import SPRACHEN, aus_header, setze_sprache, t, zuruecksetzen
from .views import STATIC


class SprachMiddleware:
    """Sprache je Anfrage: ``?sprache=`` (wird als Cookie gemerkt), Cookie, Header ``X-Sprache``, Browser-Sprache.

    Reine ASGI-Middleware, damit die gesetzte ContextVar sicher bis in Endpunkte und Fehlerbehandlung reicht.
    """

    COOKIE = "sprache"

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        aus_url = parse_qs(scope.get("query_string", b"").decode("latin-1")).get("sprache", [None])[0]
        keks = SimpleCookie(header.get("cookie", ""))
        gewaehlt = next((s for s in (aus_url, keks[self.COOKIE].value if self.COOKIE in keks else None,
                                     header.get("x-sprache")) if s in SPRACHEN), None)
        token = setze_sprache(gewaehlt or aus_header(header.get("accept-language")))
        merken = aus_url in SPRACHEN

        async def senden(nachricht) -> None:
            if merken and nachricht["type"] == "http.response.start":
                wert = f"{self.COOKIE}={aus_url}; Path=/; Max-Age=31536000; SameSite=Lax"
                nachricht.setdefault("headers", []).append((b"set-cookie", wert.encode("latin-1")))
            await send(nachricht)

        try:
            await self.app(scope, receive, senden)
        finally:
            zuruecksetzen(token)


def create_app() -> FastAPI:
    app = FastAPI(title="Parawerk", version="0.2.0",
                  description="Foto → Entwürfe → baubarer, stabiler Bauplan aus Baumarkt-Holz.")
    app.add_middleware(SprachMiddleware)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(seiten.router)
    app.include_router(entwuerfe.router)
    app.include_router(bauplan.router)
    app.include_router(kontingent.router)
    app.include_router(api_v1.router)

    # Fehler immer als {"fehler": "..."} in der Sprache der Anfrage, damit die Oberfläche sie direkt zeigen kann
    @app.exception_handler(StarletteHTTPException)
    async def http_fehler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"fehler": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def eingabe_fehler(_: Request, exc: RequestValidationError) -> JSONResponse:
        felder = ", ".join(".".join(str(p) for p in e["loc"][1:]) or t("fehler.anfrage") for e in exc.errors())
        return JSONResponse({"fehler": t("fehler.eingabe", felder=felder)}, status_code=422)

    return app


app = create_app()
