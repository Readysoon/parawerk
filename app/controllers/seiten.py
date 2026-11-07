"""Seiten-Controller: liefert die Oberfläche."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..models import speicher
from ..models.gltf import als_glb
from ..models.usdz import als_usdz
from ..models.verbrauch import datenbank
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


@router.get("/ansicht", response_class=HTMLResponse, include_in_schema=False)
def ansicht(request: Request) -> Response:
    """Nur der 3D-Viewer, eingebettet in die App: derselbe Viewer wie auf der Website, live beim Strecken."""
    return templates.TemplateResponse(request, "ansicht.html", {})


@router.get("/m/{mid}.usdz", include_in_schema=False)
def modell_usdz(mid: str, e: Einstellungen = Depends(einstellungen)) -> Response:
    gefunden = speicher.modell_laden(datenbank(e.database_url), mid)
    if not gefunden:
        return Response(status_code=404)
    return Response(als_usdz(gefunden[1]), media_type="model/vnd.usdz+zip",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/m/{mid}.glb", include_in_schema=False)
def modell_glb(mid: str, e: Einstellungen = Depends(einstellungen)) -> Response:
    gefunden = speicher.modell_laden(datenbank(e.database_url), mid)
    if not gefunden:
        return Response(status_code=404)
    return Response(als_glb(gefunden[1]), media_type="model/gltf-binary",
                    headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"})


@router.get("/m/{mid}", response_class=HTMLResponse, include_in_schema=False)
def modell_seite(mid: str, request: Request, e: Einstellungen = Depends(einstellungen)) -> Response:
    """(Nach den Dateien registriert, sonst fängt diese Route auch ``….usdz`` ab.)

    3D-Modell eines Bauplans zum Drehen, mit AR (iPhone: AR Quick Look, Android: Scene Viewer). Ziel des QR-Codes."""
    gefunden = speicher.modell_laden(datenbank(e.database_url), mid)
    if not gefunden:
        return HTMLResponse(t("fehler.modell_weg"), status_code=404)
    name, modell = gefunden
    basis = e.oeffentliche_url.rstrip("/")
    return templates.TemplateResponse(request, "modell.html", {
        "name": name, "modell": modell, "usdz": f"/m/{mid}.usdz", "glb_absolut": f"{basis}/m/{mid}.glb"})


@router.get("/gesund", include_in_schema=False)
def gesund() -> dict:
    return {"ok": True}
