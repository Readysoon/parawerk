"""App-API (v1): alles, was die Flutter-App braucht, als JSON. Bildarbeit und 3D macht der Server.

Ablauf:
1. ``POST /api/v1/entwuerfe`` mit Foto, Maske, Wunsch → Auftrag; Ergebnis: 4 fertig eingesetzte Entwürfe
2. ``POST /api/v1/entwuerfe/nachjustieren`` → Auftrag; Ergebnis: geänderter Entwurf
3. ``POST /api/v1/bauplan/lesen`` mit Entwurf und Maske → Auftrag; Ergebnis: Bauteilgraph
4. ``POST /api/v1/bauplan/berechnen`` → sofort: Bauplan als Daten und 3D-Modell (glb) als Bild-URL
5. ``POST /api/v1/bauplan/anpassen`` → Auftrag; Ergebnis: geänderter Bauteilgraph

Aufträge fragt die App mit ``GET /api/v1/auftraege/{id}`` ab (``laeuft`` → ``fertig`` oder ``fehler``).
Die Geräte-ID schickt die App im Header ``X-Geraet``, die Sprache in ``X-Sprache``.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from PIL import Image

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..models import speicher
from ..models.dxf import teile_als_dxf
from ..models.gltf import als_glb
from ..models.verbrauch import datenbank
from ..services import bildarbeit as ba
from ..services.auftraege import starten
from ..services.bild_ki import BildKI
from ..services.fehler import DienstFehler
from ..services.konstrukteur import Konstrukteur
from ..services.kostendeckel import Kostendeckel, Kunde
from ..services.prompts import bearbeitung_prompt, inpaint_prompt
from ..views import STATIC
from ..views.praesentation import bauplan_ansicht, modell_3d
from .abhaengigkeiten import bild_ki, konstrukteur, kostendeckel, kunde
from .bauplan import _graph, _rechnen
from .kontingent import erstatten, kontingent, reservieren
from .schemas_v1 import (AuftragAntwort, AuftragStand, BauplanAntwort, BerechnenV1, EntwuerfeV1, LesenV1,
                         NachjustierenV1)
from .schemas import AnpassenAnfrage

router = APIRouter(prefix="/api/v1", tags=["App-API v1"])
router.add_api_route("/kontingent", kontingent, methods=["GET"])


def _db(e: Einstellungen):
    return datenbank(e.database_url)


def _bild(db, bid: str) -> Image.Image:
    gefunden = speicher.bild_laden(db, bid)
    if not gefunden:
        raise HTTPException(404, t("fehler.bild_fehlt"))
    return ba.aus_bytes(gefunden[0])


def _url(bid: str) -> str:
    return f"/api/v1/bilder/{bid}"


def _quelle(src: str) -> Image.Image:
    """Ergebnis der Bild-KI: data-URL (Replicate) oder Pfad unter /static (Demo)."""
    if src.startswith("/static/"):
        datei = (STATIC / src.removeprefix("/static/")).resolve()
        if STATIC.resolve() not in datei.parents:
            raise DienstFehler(t("fehler.bild_kaputt"))
        return ba.aus_bytes(Path(datei).read_bytes())
    return ba.aus_data_url(src)


@router.get("/bilder/{bid}")
async def bild(bid: str, e: Einstellungen = Depends(einstellungen)) -> Response:
    """Gespeichertes Bild (Foto, Maske, Entwurf) oder 3D-Modell. Die ID ist zufällig und nicht erratbar."""
    gefunden = await run_in_threadpool(speicher.bild_laden, _db(e), bid)
    if not gefunden:
        raise HTTPException(404, t("fehler.bild_fehlt"))
    daten, mime = gefunden
    return Response(daten, media_type=mime, headers={"Cache-Control": "private, max-age=604800, immutable"})


@router.get("/auftraege/{aid}", response_model=AuftragStand)
async def auftrag(aid: str, k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> AuftragStand:
    a = await run_in_threadpool(speicher.auftrag_laden, _db(e), aid)
    if not a or not secrets.compare_digest(a["geraet"], k.geraet):
        raise HTTPException(404, t("fehler.auftrag_fehlt"))
    return AuftragStand(id=a["id"], art=a["art"], status=a["status"], ergebnis=a["ergebnis"], fehler=a["fehler"])


@router.post("/entwuerfe", response_model=AuftragAntwort, status_code=202)
async def entwuerfe(anfrage: EntwuerfeV1, ki: BildKI = Depends(bild_ki), kon: Konstrukteur = Depends(konstrukteur),
                    deckel: Kostendeckel = Depends(kostendeckel), k: Kunde = Depends(kunde),
                    e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Foto und Maske speichern, dann im Hintergrund Entwürfe malen lassen und ins Foto einsetzen."""
    db = _db(e)
    await run_in_threadpool(speicher.aufraeumen, db)
    try:
        foto = ba.foto_vorbereiten(ba.aus_data_url(anfrage.foto) if anfrage.foto else _bild(db, anfrage.foto_id))
        maske = ba.maske_vorbereiten(ba.aus_data_url(anfrage.maske) if anfrage.maske else _bild(db, anfrage.maske_id),
                                     foto.size)
    except DienstFehler as err:
        raise HTTPException(400, str(err)) from err
    if not ba.rahmen(maske):
        raise HTTPException(400, t("fehler.nichts_markiert"))
    foto_id = anfrage.foto_id or await run_in_threadpool(speicher.bild_speichern, db, k.geraet, ba.jpeg(foto), "image/jpeg")
    maske_id = anfrage.maske_id or await run_in_threadpool(speicher.bild_speichern, db, k.geraet, ba.png(maske), "image/png")
    eintrag = None if ki.demo else await reservieren(deckel, "runde", k)

    async def arbeit() -> dict:
        foto_url = ba.als_data_url(ba.jpeg(foto), "image/jpeg")
        maske_url = ba.als_data_url(ba.png(ba.ki_maske(maske)), "image/png")
        prompt = inpaint_prompt(anfrage.wunsch)
        if not ki.demo:
            try:
                prompt = await kon.bild_prompt(anfrage.wunsch, foto_url, maske_url)
            except DienstFehler:
                pass  # dann eben der wörtliche Wunsch
        seeds = [secrets.randbelow(10**9) for _ in range(e.anzahl_entwuerfe)]
        bilder = await ki.entwerfen(foto_url, maske_url, prompt, seeds)
        ids = []
        for src in bilder:
            fertig = await run_in_threadpool(ba.einsetzen, foto, maske, _quelle(src))
            ids.append(await run_in_threadpool(speicher.bild_speichern, db, k.geraet, ba.jpeg(fertig, 90), "image/jpeg"))
        return {"demo": ki.demo, "prompt": prompt,
                "entwuerfe": [{"id": i, "url": _url(i), "index": n} for n, i in enumerate(ids)]}

    aid = await starten(db, k.geraet, "entwuerfe", arbeit, "fehler.entwuerfe", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid, foto_id=foto_id, maske_id=maske_id)


@router.post("/entwuerfe/nachjustieren", response_model=AuftragAntwort, status_code=202)
async def nachjustieren(anfrage: NachjustierenV1, ki: BildKI = Depends(bild_ki), kon: Konstrukteur = Depends(konstrukteur),
                        deckel: Kostendeckel = Depends(kostendeckel), k: Kunde = Depends(kunde),
                        e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Einen Entwurf per Text ändern; eingesetzt wird wieder nur der markierte Bereich."""
    if ki.demo:
        raise HTTPException(501, t("fehler.nj_demo"))
    db = _db(e)
    foto, maske, entwurf = _bild(db, anfrage.foto_id), _bild(db, anfrage.maske_id).convert("L"), _bild(db, anfrage.entwurf_id)
    eintrag = await reservieren(deckel, "nachjustieren", k)

    async def arbeit() -> dict:
        entwurf_url = ba.als_data_url(ba.jpeg(entwurf, 90), "image/jpeg")
        try:
            prompt = await kon.bearbeitungs_prompt(anfrage.wunsch, anfrage.anpassung, entwurf_url)
        except DienstFehler:
            prompt = bearbeitung_prompt(anfrage.anpassung)
        neu = await ki.bearbeiten(entwurf_url, prompt, secrets.randbelow(10**9))
        fertig = await run_in_threadpool(ba.einsetzen, foto, maske, _quelle(neu))
        bid = await run_in_threadpool(speicher.bild_speichern, db, k.geraet, ba.jpeg(fertig, 90), "image/jpeg")
        return {"prompt": prompt, "entwurf": {"id": bid, "url": _url(bid)}}

    aid = await starten(db, k.geraet, "nachjustieren", arbeit, "fehler.nachjustieren", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid)


@router.post("/bauplan/lesen", response_model=AuftragAntwort, status_code=202)
async def lesen(anfrage: LesenV1, kon: Konstrukteur = Depends(konstrukteur), deckel: Kostendeckel = Depends(kostendeckel),
                k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Konstruktion aus dem gewählten Entwurf lesen. Den Ausschnitt um den markierten Bereich schneidet der Server."""
    db = _db(e)
    entwurf, maske = _bild(db, anfrage.entwurf_id), _bild(db, anfrage.maske_id).convert("L")
    eintrag = None if kon.demo else await reservieren(deckel, "lesen", k)

    async def arbeit() -> dict:
        teil = ba.ausschnitt(entwurf, maske.resize(entwurf.size) if maske.size != entwurf.size else maske)
        graph = await kon.lesen(ba.als_data_url(ba.jpeg(teil, 90), "image/jpeg"), anfrage.bereich, anfrage.demo_index)
        return {"demo": kon.demo, "graph": graph}

    aid = await starten(db, k.geraet, "lesen", arbeit, "fehler.lesen", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid)


@router.post("/bauplan/anpassen", response_model=AuftragAntwort, status_code=202)
async def anpassen(anfrage: AnpassenAnfrage, kon: Konstrukteur = Depends(konstrukteur),
                   deckel: Kostendeckel = Depends(kostendeckel), k: Kunde = Depends(kunde),
                   e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Bauteilgraph nach einem Wunsch in Worten ändern."""
    if kon.demo:
        raise HTTPException(501, t("fehler.anpassen_demo"))
    graph = _graph(anfrage.graph)
    eintrag = await reservieren(deckel, "anpassen", k)

    async def arbeit() -> dict:
        return {"graph": await kon.anpassen(graph, anfrage.wunsch)}

    aid = await starten(_db(e), k.geraet, "anpassen", arbeit, "fehler.aenderung", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid)


@router.post("/bauplan/berechnen", response_model=BauplanAntwort)
async def berechnen(anfrage: BerechnenV1, k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> BauplanAntwort:
    """Bauteilgraph → baubarer Bauplan als Daten, dazu das 3D-Modell als glb-Datei (URL)."""
    graph = _graph(anfrage.graph)
    ergebnis = await run_in_threadpool(_rechnen, graph, anfrage.bereich, anfrage.sortiment or e.sortiment)
    ansicht = bauplan_ansicht(ergebnis, graph, anfrage.bereich)
    ansicht.pop("graph_json", None)
    modell = modell_3d(ergebnis)
    glb = await run_in_threadpool(speicher.bild_speichern, _db(e), k.geraet, als_glb(modell), "model/gltf-binary")
    return BauplanAntwort(name=graph["name"], offene_punkte=ergebnis.offene_punkte, bauplan=ansicht,
                          modell=modell, modell_glb=_url(glb), plan=ergebnis.plan)


@router.post("/bauplan/dxf")
async def dxf(anfrage: BerechnenV1, e: Einstellungen = Depends(einstellungen)) -> Response:
    ergebnis = await run_in_threadpool(_rechnen, _graph(anfrage.graph), anfrage.bereich, anfrage.sortiment or e.sortiment)
    return Response(teile_als_dxf(ergebnis.members), media_type="application/dxf",
                    headers={"Content-Disposition": 'attachment; filename="parawerk.dxf"'})
