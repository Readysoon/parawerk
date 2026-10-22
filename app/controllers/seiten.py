"""Seiten-Controller: liefert die Oberfläche."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..config import Einstellungen, einstellungen
from ..views import templates

router = APIRouter()

WUENSCHE = ["Daybed aus Latten mit Polstern", "Regal bis unter die Decke", "Sitzbank mit Stauraum", "niedriges Sideboard"]


@router.get("/", response_class=HTMLResponse)
def startseite(request: Request, e: Einstellungen = Depends(einstellungen)) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {
        "wuensche": WUENSCHE,
        "demo_bilder": not e.bild_ki_aktiv,
        "demo_lesen": not e.claude_aktiv,
        "anzahl_entwuerfe": e.anzahl_entwuerfe,
    })


@router.get("/gesund", include_in_schema=False)
def gesund() -> dict:
    return {"ok": True}
