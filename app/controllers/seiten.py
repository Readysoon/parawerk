"""Seiten-Controller: liefert die Oberfläche."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..views import templates
from .abhaengigkeiten import ADMIN, JAHR, geraete_id

router = APIRouter()

WUENSCHE = ["ui.wunsch.1", "ui.wunsch.2", "ui.wunsch.3", "ui.wunsch.4"]


@router.get("/", response_class=HTMLResponse)
def startseite(request: Request, schluessel: str = "", e: Einstellungen = Depends(einstellungen)) -> Response:
    if schluessel:  # Admin-Schlüssel als Cookie merken und aus der Adresszeile entfernen
        weiter = RedirectResponse("/", status_code=303)
        if e.admin_schluessel and secrets.compare_digest(schluessel.encode(), e.admin_schluessel.encode()):
            weiter.set_cookie(ADMIN, schluessel, max_age=JAHR, httponly=True, samesite="lax",
                              secure=request.url.scheme == "https")
        return weiter
    seite = templates.TemplateResponse(request, "index.html", {
        "wuensche": [t(k) for k in WUENSCHE],
        "demo_bilder": not e.bild_ki_aktiv,
        "demo_lesen": not e.claude_aktiv,
        "anzahl_entwuerfe": e.anzahl_entwuerfe,
    })
    geraete_id(request, seite)  # Geräte-ID gleich beim ersten Besuch vergeben
    return seite


@router.get("/gesund", include_in_schema=False)
def gesund() -> dict:
    return {"ok": True}
