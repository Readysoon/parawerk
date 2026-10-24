"""Seiten-Controller: liefert die Oberfläche."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..views import templates

router = APIRouter()

WUENSCHE = ["ui.wunsch.1", "ui.wunsch.2", "ui.wunsch.3", "ui.wunsch.4"]


@router.get("/", response_class=HTMLResponse)
def startseite(request: Request, e: Einstellungen = Depends(einstellungen)) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {
        "wuensche": [t(k) for k in WUENSCHE],
        "demo_bilder": not e.bild_ki_aktiv,
        "demo_lesen": not e.claude_aktiv,
        "anzahl_entwuerfe": e.anzahl_entwuerfe,
    })


@router.get("/gesund", include_in_schema=False)
def gesund() -> dict:
    return {"ok": True}
