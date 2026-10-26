"""Welche Dienste die Controller bekommen. Ohne API-Schlüssel laufen die Demo-Dienste.

In Tests lassen sie sich über ``app.dependency_overrides`` ersetzen.
"""
from __future__ import annotations

import re
import secrets

from fastapi import Depends, Request, Response

from ..config import Einstellungen, einstellungen
from ..services.bild_ki import BildKI, DemoBildKI, ReplicateFluxFill
from ..models.verbrauch import datenbank
from ..services.konstrukteur import ClaudeKonstrukteur, DemoKonstrukteur, Konstrukteur
from ..services.kostendeckel import Kostendeckel, Kunde
from ..services.tiefe import DemoTiefe, ReplicateTiefe, TiefenKI

GERAET = "geraet"  # Cookie mit der Geräte-ID
ADMIN = "admin"  # Cookie mit dem Admin-Schlüssel
JAHR = 365 * 24 * 3600


def bild_ki(e: Einstellungen = Depends(einstellungen)) -> BildKI:
    return ReplicateFluxFill(e.replicate_api_token, e.replicate_model, e.replicate_edit_model) if e.bild_ki_aktiv else DemoBildKI()


def tiefen_ki(e: Einstellungen = Depends(einstellungen)) -> TiefenKI:
    return ReplicateTiefe(e.replicate_api_token, e.replicate_tiefe_model) if e.bild_ki_aktiv else DemoTiefe()


def konstrukteur(e: Einstellungen = Depends(einstellungen)) -> Konstrukteur:
    return ClaudeKonstrukteur(e.anthropic_api_key, e.anthropic_model) if e.claude_aktiv else DemoKonstrukteur()


def kostendeckel(e: Einstellungen = Depends(einstellungen)) -> Kostendeckel:
    return Kostendeckel(datenbank(e.database_url), e)


def client_ip(request: Request) -> str:
    """Echte IP hinter dem fly.io-Proxy."""
    h = request.headers
    return (h.get("fly-client-ip") or h.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "") or "?")[:64]


GUELTIGE_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def geraete_id(request: Request, response: Response) -> str:
    """Geräte-ID: von der App im Header ``X-Geraet``, im Browser aus dem Cookie. Fehlt sie, wird ein Cookie vergeben."""
    kopf = request.headers.get("x-geraet", "")
    if GUELTIGE_ID.match(kopf):
        return kopf
    gid = request.cookies.get(GERAET, "")
    if not GUELTIGE_ID.match(gid):
        gid = secrets.token_urlsafe(16)
        response.set_cookie(GERAET, gid, max_age=JAHR, httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return gid


def kunde(request: Request, response: Response, e: Einstellungen = Depends(einstellungen)) -> Kunde:
    schluessel = request.cookies.get(ADMIN, "")
    admin = bool(e.admin_schluessel) and secrets.compare_digest(schluessel.encode(), e.admin_schluessel.encode())
    return Kunde(geraet=geraete_id(request, response), ip=client_ip(request), admin=admin)
