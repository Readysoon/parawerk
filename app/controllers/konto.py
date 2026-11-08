"""Konto: anmelden mit Apple oder Google, abmelden, löschen, Stand; Baupläne mit einem Code freischalten."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..config import Einstellungen, einstellungen
from ..i18n import sprache, t
from ..models import analyse, konten
from ..models import verbrauch as v
from ..models.verbrauch import datenbank
from ..services.anmeldung import AnmeldeFehler, Identitaet, pruefen
from ..services.kostendeckel import Gesperrt, Kostendeckel, Kunde
from .abhaengigkeiten import JAHR, SITZUNG, geraete_id, kunde, sitzungs_token

router = APIRouter(prefix="/api/v1")
log = logging.getLogger("parawerk.konto")


class AnmeldeAnfrage(BaseModel):
    id_token: str = Field(min_length=20, max_length=8000)
    email: str | None = Field(None, max_length=254, description="Apple: nur beim ersten Anmelden, falls nicht im Token")


class FreischaltAnfrage(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    graph: dict
    entwurf_id: str | None = Field(None, max_length=32)


LOKAL = ("127.0.0.1", "::1", "localhost", "testclient")


def demo_anmeldung(request: Request, e: Einstellungen) -> bool:
    """Anmelden ohne Apple/Google: im Demo-Modus (ohne KI-Schlüssel) immer, sonst nur mit ``stufen_simulieren``
    und nur direkt vom selben Computer (lokaler Server, keine Weiterleitung über einen Proxy wie bei fly.io)."""
    if not (e.claude_aktiv or e.bild_ki_aktiv):
        return True
    h = request.headers
    direkt = not (h.get("fly-client-ip") or h.get("x-forwarded-for") or h.get("fly-region"))
    return e.stufen_simulieren and direkt and bool(request.client) and request.client.host in LOKAL


def stufen(k: Kunde, e: Einstellungen, request: Request) -> dict:
    return {"email": k.email, "konto_pflicht": e.konto_pflicht, "bezahlung_pflicht": e.bezahlung_pflicht,
            "apple_web": e.apple_web_client_id or None, "google_web": e.google_web_client_id or None,
            "demo": demo_anmeldung(request, e)}


@router.get("/konto")
async def konto(request: Request, k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> dict:
    """Angemeldet als …, welche Schranken gelten und welche Anmelde-Knöpfe die Website zeigt."""
    return stufen(k, e, request)


def pruefer(request: Request, e: Einstellungen = Depends(einstellungen)):
    """Prüft ID-Tokens (in Tests ersetzbar). Zusätzlich ``demo``, wenn ``demo_anmeldung`` es erlaubt."""
    def pruefe(anbieter: str, id_token: str) -> Identitaet:
        if anbieter == "demo":
            if not demo_anmeldung(request, e):
                raise AnmeldeFehler("Demo-Anmeldung nur im Demo-Modus oder lokal mit STUFEN_SIMULIEREN")
            return Identitaet("demo", id_token[:64], None)
        return pruefen(anbieter, id_token, e.client_ids(anbieter))
    return pruefe


def _uebernehmen(db, geraet: str, konto_id: int) -> None:
    """Was das Gerät vor der Anmeldung hatte (eingelöste Codes, Freischaltungen), gehört jetzt dem Konto."""
    wer = f"k-{konto_id}"
    with db.begin() as c:
        for tab, spalte in ((v.einloesungen, "geraet"), (konten.freischaltungen, "wer")):
            for z in c.execute(tab.select().where(tab.c[spalte] == geraet)).all():
                daten = {**dict(z._mapping), spalte: wer}
                daten.pop("id")
                try:
                    with c.begin_nested():
                        c.execute(tab.insert().values(**daten))
                except Exception:  # noqa: BLE001  (hat das Konto schon)
                    pass


@router.post("/konto/anmelden/{anbieter}")
async def anmelden(anbieter: str, anfrage: AnmeldeAnfrage, request: Request, response: Response,
                   e: Einstellungen = Depends(einstellungen), pruefe=Depends(pruefer)) -> dict:
    """ID-Token von Apple oder Google gegen eine Parawerk-Sitzung tauschen."""
    if anbieter not in konten.ANBIETER:
        raise HTTPException(404, t("fehler.anmeldung"))
    try:
        ich = await run_in_threadpool(pruefe, anbieter, anfrage.id_token)
    except AnmeldeFehler as err:
        log.info("Anmeldung %s abgelehnt: %s", anbieter, err)
        raise HTTPException(401, t("fehler.anmeldung")) from err
    db = datenbank(e.database_url)
    token = await run_in_threadpool(konten.anmelden, db, ich.anbieter, ich.sub, ich.email or anfrage.email)
    konto_id, name = konten.konto_zur_sitzung(db, token)
    await run_in_threadpool(_uebernehmen, db, geraete_id(request, response), konto_id)
    response.set_cookie(SITZUNG, token, max_age=JAHR, httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return {"token": token, "email": name}


@router.post("/konto/abmelden")
async def abmelden(request: Request, response: Response, e: Einstellungen = Depends(einstellungen)) -> dict:
    token = sitzungs_token(request)
    if token:
        await run_in_threadpool(konten.abmelden, datenbank(e.database_url), token)
    response.delete_cookie(SITZUNG)
    return {"email": None}


@router.delete("/konto")
async def loeschen(response: Response, k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> dict:
    """Konto mit allen Daten löschen (Apple verlangt das für Apps mit Konto)."""
    if not k.konto:
        raise HTTPException(401, t("fehler.konto_noetig"))
    await run_in_threadpool(konten.konto_loeschen, datenbank(e.database_url), k.konto)
    response.delete_cookie(SITZUNG)
    return {"email": None}


@router.post("/freischalten")
async def freischalten(anfrage: FreischaltAnfrage, k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> dict:
    """Einen Bauplan mit einem Code freischalten (z. B. für Tester und Partner). Später auch nach einer Zahlung."""
    code = anfrage.code.strip().upper()
    plaene = e.code_plaene.get(code, 0)
    if code not in e.codes or plaene <= 0:
        raise HTTPException(404, t("fehler.code_unbekannt"))
    db = datenbank(e.database_url)
    try:  # zählt wie ein Testcode: höchstens so viele Geräte bzw. Konten, wie der Code erlaubt
        await run_in_threadpool(Kostendeckel(db, e).code_einloesen, code, k)
    except Gesperrt as g:
        raise HTTPException(g.status, str(g)) from g
    plan = konten.plan_schluessel(anfrage.entwurf_id, anfrage.graph)
    if await run_in_threadpool(konten.freigeschaltet, db, k.geraet, plan):
        return {"freigeschaltet": True}
    if await run_in_threadpool(konten.freischaltungen_mit, db, k.geraet, f"code:{code}") >= plaene:
        raise HTTPException(409, t("fehler.code_plaene_voll", n=plaene))
    await run_in_threadpool(konten.freischalten, db, k.geraet, plan, f"code:{code}")
    await run_in_threadpool(analyse.eintragen, db, "freigeschaltet", {
        "quelle": "code", "entwurf": analyse.lauf(anfrage.entwurf_id), "name": str(anfrage.graph.get("name", ""))[:80],
        "kategorie": anfrage.graph.get("kategorie"), "sitz": anfrage.graph.get("sitz") or "latten"},
        sprache=sprache(), demo=not e.claude_aktiv)
    return {"freigeschaltet": True}
