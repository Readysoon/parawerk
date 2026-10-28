"""API (v1) für Website und Flutter-App: alles als JSON. Bildarbeit und 3D macht der Server.

Ablauf:
1. ``POST /api/v1/entwuerfe`` mit Foto, Maske, Wunsch → Auftrag; Ergebnis: 4 fertig eingesetzte Entwürfe
2. ``POST /api/v1/entwuerfe/nachjustieren`` → Auftrag; Ergebnis: geänderter Entwurf
3. ``POST /api/v1/bauplan/lesen`` mit Entwurf und Maske → Auftrag; Ergebnis: Bauteilgraph
4. ``POST /api/v1/bauplan/berechnen`` → sofort: Bauplan als Daten und 3D-Modell (glb) als Bild-URL
5. ``POST /api/v1/bauplan/anpassen`` → Auftrag; Ergebnis: geänderter Bauteilgraph

Messen (optional, vor Schritt 1): ``POST /api/v1/fotos`` lädt das Foto hoch und schätzt im Hintergrund die Tiefe;
``POST /api/v1/masse`` rechnet aus einer gemessenen Strecke Breite, Tiefe und Höhe des markierten Bereichs.

Aufträge fragt die App mit ``GET /api/v1/auftraege/{id}`` ab (``laeuft`` → ``fertig`` oder ``fehler``).
Die Geräte-ID schickt die App im Header ``X-Geraet``, die Sprache in ``X-Sprache``.
"""
from __future__ import annotations

import logging
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
import numpy as np
from PIL import Image

from ..config import Einstellungen, einstellungen
from ..i18n import sprache, t
from ..models import analyse, speicher
from ..models.bauteilgraph import GraphFehler, bereinigen
from ..models.dxf import teile_als_dxf
from ..models.engine import Ergebnis, berechnen as engine_berechnen
from ..models.ansicht import modellbild
from ..models.gltf import als_glb
from ..models.usdz import als_usdz
from ..models.raum import Messung, Tiefe, bereich_messen, flach
from ..models.verbrauch import datenbank
from ..services import bildarbeit as ba
from ..services.auftraege import starten
from ..services.bild_ki import BildKI
from ..services.fehler import DienstFehler
from ..services.konstrukteur import Konstrukteur
from ..services.kostendeckel import Gesperrt, Kostendeckel, Kunde
from ..services.prompts import bearbeitung_prompt, inpaint_prompt
from ..services.tiefe import TiefenKI
from ..views import STATIC, templates
from ..views.pdf import bauplan_pdf
from ..views.praesentation import bauplan_ansicht, modell_3d
from .abhaengigkeiten import bild_ki, konstrukteur, kostendeckel, kunde, tiefen_ki
from .schemas import (AnpassenAnfrage, CodeAnfrage, AuftragAntwort, AuftragStand, BauplanAntwort, BerechnenV1, EntwuerfeV1,
                      FotoV1, LesenV1, MasseAntwort, MasseV1, NachjustierenV1, PdfV1)

router = APIRouter(prefix="/api/v1", tags=["API v1"])
MIME_TIEFE = "application/x-parawerk-tiefe"  # Tiefenkarte (npz) in der Bilder-Tabelle
log = logging.getLogger("parawerk.api")


def _db(e: Einstellungen):
    return datenbank(e.database_url)


def _graph(roh: dict) -> dict:
    try:
        return bereinigen(roh)
    except GraphFehler as err:
        raise HTTPException(422, str(err)) from err


def _rechnen(graph: dict, bereich: list[float], sortiment: str, schnell: bool = False) -> Ergebnis:
    try:
        return engine_berechnen(graph, bereich, sortiment, schnell)
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as err:
        raise HTTPException(422, t("fehler.modell", art=type(err).__name__)) from err


async def reservieren(deckel: Kostendeckel, art: str, k: Kunde) -> int:
    """Kosten vor dem Aufruf eintragen; ist das Kontingent oder Budget erschöpft, gibt es eine lesbare Fehlermeldung."""
    try:
        return await run_in_threadpool(deckel.reservieren, art, k)
    except Gesperrt as g:
        raise HTTPException(g.status, str(g)) from g


async def erstatten(deckel: Kostendeckel, eintrag: int | None) -> None:
    await run_in_threadpool(deckel.erstatten, eintrag)


@router.get("/kontingent")
async def kontingent(k: Kunde = Depends(kunde), deckel: Kostendeckel = Depends(kostendeckel),
                     e: Einstellungen = Depends(einstellungen)) -> dict:
    """Verbleibende Gratis-Runden und -Änderungen (``null`` = unbegrenzt bzw. Demo-Modus)."""
    if not e.bild_ki_aktiv:
        return {"runden": None, "nachjustieren": None}
    return await run_in_threadpool(deckel.stand, k)


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


@router.post("/code")
async def code(anfrage: CodeAnfrage, k: Kunde = Depends(kunde), deckel: Kostendeckel = Depends(kostendeckel)) -> dict:
    """Testcode einlösen: mehr Gratis-Runden für dieses Gerät. Antwort wie ``/kontingent``."""
    try:
        return await run_in_threadpool(deckel.code_einloesen, anfrage.code, k)
    except Gesperrt as g:
        raise HTTPException(g.status, str(g)) from g


@router.get("/bilder/{bid}")
@router.get("/bilder/{bid}/{dateiname}")
async def bild(bid: str, e: Einstellungen = Depends(einstellungen)) -> Response:
    """Gespeichertes Bild (Foto, Maske, Entwurf) oder 3D-Modell. Die ID ist zufällig und nicht erratbar.

    Der Dateiname ist egal (z. B. ``…/parawerk.usdz``); manche Viewer erkennen das Format nur an der Endung.
    """
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


@router.post("/fotos", response_model=AuftragAntwort, status_code=202)
async def fotos(anfrage: FotoV1, tki: TiefenKI = Depends(tiefen_ki), deckel: Kostendeckel = Depends(kostendeckel),
                k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Foto hochladen (``foto_id`` gilt dann für ``/entwuerfe``). Im Hintergrund schätzt die Tiefen-KI die Entfernungen.

    Ergebnis des Auftrags: ``tiefe_id`` für ``/masse`` und ``flach``. ``flach=true`` heißt: keine echte Tiefe (Demo,
    Limit oder Fehler), gemessen wird dann nur in der Ebene der Messung, wie mit einem Lineal auf dem Foto.
    """
    db = _db(e)
    await run_in_threadpool(speicher.aufraeumen, db)
    try:
        foto = ba.foto_vorbereiten(ba.aus_data_url(anfrage.foto))
    except DienstFehler as err:
        raise HTTPException(400, str(err)) from err
    foto_id = await run_in_threadpool(speicher.bild_speichern, db, k.geraet, ba.jpeg(foto), "image/jpeg")
    eintrag, mit_ki = None, not tki.demo
    if mit_ki:
        try:
            eintrag = await reservieren(deckel, "tiefe", k)
        except HTTPException:
            mit_ki = False  # Limit oder Budget: Messen geht trotzdem, nur ohne Tiefe

    async def arbeit() -> dict:
        tiefe = None
        if mit_ki:
            try:
                tiefe = await tki.schaetzen(foto)
            except DienstFehler as err:
                log.warning("Tiefe nicht geschätzt: %s", err)
                await erstatten(deckel, eintrag)
        if tiefe is None:  # Demo: Ersatz des Demo-Dienstes; sonst bei Limit oder Fehler: flach
            tiefe = await tki.schaetzen(foto) if tki.demo else flach(*foto.size)
        tid = await run_in_threadpool(speicher.bild_speichern, db, k.geraet, tiefe.als_bytes(), MIME_TIEFE)
        return {"tiefe_id": tid, "flach": tiefe.flach}

    aid = await starten(db, k.geraet, "tiefe", arbeit, "fehler.tiefe", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid, foto_id=foto_id)


@router.post("/masse", response_model=MasseAntwort)
async def masse(anfrage: MasseV1, e: Einstellungen = Depends(einstellungen)) -> MasseAntwort:
    """Breite, Tiefe und Höhe des markierten Bereichs aus der Tiefenkarte und 1–3 gemessenen Strecken.

    Kostet nichts (rechnet nur). Werte, die sich nicht messen lassen, sind ``null``: dann bleibt das Eingabefeld, wie es ist.
    """
    db = _db(e)
    gefunden = await run_in_threadpool(speicher.bild_laden, db, anfrage.tiefe_id)
    if not gefunden or gefunden[1] != MIME_TIEFE:
        raise HTTPException(404, t("fehler.bild_fehlt"))
    try:
        tiefe = Tiefe.aus_bytes(gefunden[0])
        roh = ba.aus_data_url(anfrage.maske) if anfrage.maske else _bild(db, anfrage.maske_id)
    except DienstFehler as err:
        raise HTTPException(400, str(err)) from err
    maske = np.asarray(ba.maske_vorbereiten(roh, roh.size))
    if not (maske > 127).any():
        raise HTTPException(400, t("fehler.nichts_markiert"))
    messungen = [Messung((m.a[0], m.a[1]), (m.b[0], m.b[1]), m.mm) for m in anfrage.messungen]
    ergebnis = await run_in_threadpool(bereich_messen, tiefe, maske, messungen)
    return MasseAntwort(bereich=ergebnis.bereich, abweichung=ergebnis.abweichung,
                        nachmessen="masse.nachmessen" in ergebnis.hinweise, hinweise=[t(h) for h in ergebnis.hinweise])


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
        await run_in_threadpool(analyse.eintragen, db, "entwuerfe", {"wunsch": anfrage.wunsch, "prompt": prompt,
                                                                      "anzahl": len(ids)},
                                lauf_id=analyse.lauf(maske_id), sprache=sprache(), demo=ki.demo)
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
        await run_in_threadpool(analyse.eintragen, db, "nachjustiert", {"wunsch": anfrage.wunsch,
                                                                         "anpassung": anfrage.anpassung},
                                lauf_id=analyse.lauf(anfrage.maske_id), sprache=sprache())
        return {"prompt": prompt, "entwurf": {"id": bid, "url": _url(bid)}}

    aid = await starten(db, k.geraet, "nachjustieren", arbeit, "fehler.nachjustieren", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid)


async def _selbstkontrolle(kon: Konstrukteur, entwurf_url: str, graph: dict, bereich: list[float], sortiment: str,
                           runden: int, weitere_runde) -> tuple[dict, dict | None]:
    """Modell berechnen und zeichnen, Claude vergleicht es mit dem Entwurf und korrigiert den Graph.

    Die erste Runde läuft immer, jede weitere nur, wenn Claude etwas korrigiert hat und die Endkontrolle der Engine
    danach noch etwas meldet. ``weitere_runde()`` bucht die Kosten und sagt, ob das Budget sie noch erlaubt.
    Geht etwas schief, bleibt der letzte gute Stand; die Kontrolle ist ein Zusatz, kein Muss.
    """
    maengel: list[str] = []
    passt = True
    durchgefuehrt = 0
    for runde in range(max(1, runden)):
        try:
            ergebnis = await run_in_threadpool(engine_berechnen, graph, bereich, sortiment)
            meldungen = [c["t"] for c in ergebnis.checks if c["ok"] is False]
            if runde > 0 and (not meldungen or not await weitere_runde()):
                break
            bild = await run_in_threadpool(modellbild, modell_3d(ergebnis))
            antwort = await kon.pruefen(entwurf_url, ba.als_data_url(ba.png(bild), "image/png"), graph, bereich,
                                        meldungen)
        except (DienstFehler, GraphFehler, ValueError, KeyError, IndexError, ZeroDivisionError) as err:
            log.warning("Selbstkontrolle Runde %d übersprungen: %s", runde + 1, err)
            break
        durchgefuehrt += 1
        if antwort["passt"]:
            break
        passt = False
        graph = antwort["graph"]
        maengel += [m for m in antwort["maengel"] if m not in maengel]
    if not durchgefuehrt:
        return graph, None
    return graph, {"passt": passt, "maengel": maengel, "runden": durchgefuehrt}


@router.post("/bauplan/lesen", response_model=AuftragAntwort, status_code=202)
async def lesen(anfrage: LesenV1, kon: Konstrukteur = Depends(konstrukteur), deckel: Kostendeckel = Depends(kostendeckel),
                k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> AuftragAntwort:
    """Konstruktion aus dem gewählten Entwurf lesen. Den Ausschnitt um den markierten Bereich schneidet der Server."""
    db = _db(e)
    entwurf, maske = _bild(db, anfrage.entwurf_id), _bild(db, anfrage.maske_id).convert("L")
    eintrag = None if kon.demo else await reservieren(deckel, "lesen", k)

    async def arbeit() -> dict:
        teil = ba.ausschnitt(entwurf, maske.resize(entwurf.size) if maske.size != entwurf.size else maske)
        teil_url = ba.als_data_url(ba.jpeg(teil, 90), "image/jpeg")
        graph = await kon.lesen(teil_url, anfrage.bereich, anfrage.demo_index)
        pruefung = None
        if not kon.demo and e.selbstkontrolle:
            async def weitere_runde() -> bool:
                try:
                    await run_in_threadpool(deckel.reservieren, "kontrolle", k)
                    return True
                except Gesperrt:  # Tagesbudget erreicht: bei einer Runde bleiben
                    return False

            graph, pruefung = await _selbstkontrolle(kon, teil_url, graph, anfrage.bereich, e.sortiment,
                                                     e.kontrollrunden, weitere_runde)
        await run_in_threadpool(analyse.eintragen, db, "gelesen", {"bereich": anfrage.bereich, "graph": graph,
                                                                    "selbstkontrolle": pruefung},
                                lauf_id=analyse.lauf(anfrage.maske_id), sprache=sprache(), demo=kon.demo)
        return {"demo": kon.demo, "graph": graph, "pruefung": pruefung}

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
        neu = await kon.anpassen(graph, anfrage.wunsch)
        await run_in_threadpool(analyse.eintragen, _db(e), "angepasst", {"wunsch": anfrage.wunsch, "vorher": graph,
                                                                          "nachher": neu}, sprache=sprache())
        return {"graph": neu}

    aid = await starten(_db(e), k.geraet, "anpassen", arbeit, "fehler.aenderung", lambda: erstatten(deckel, eintrag))
    return AuftragAntwort(auftrag=aid)


@router.post("/bauplan/berechnen", response_model=BauplanAntwort, response_model_exclude_none=True)
async def berechnen(anfrage: BerechnenV1, mit_glb: bool = True, mit_html: bool = False, schnell: bool = False,
                    k: Kunde = Depends(kunde), e: Einstellungen = Depends(einstellungen)) -> BauplanAntwort:
    """Bauteilgraph → baubarer Bauplan als Daten, dazu das 3D-Modell als glb-Datei (URL).

    ``mit_html=true`` liefert zusätzlich den fertigen Bauplan-Ausschnitt für die Website,
    ``mit_glb=false`` spart die glb-Datei, wenn die Anzeige die Quader selbst zeichnet.
    ``schnell=true``: Vorschau beim Strecken mit einem Regler (``graph.ziel``), etwas weniger genau, dafür flüssig.
    """
    graph = _graph(anfrage.graph)
    ergebnis = await run_in_threadpool(_rechnen, graph, anfrage.bereich, anfrage.sortiment or e.sortiment, schnell)
    ansicht = bauplan_ansicht(ergebnis, graph, anfrage.bereich)
    html = templates.get_template("teile/bauplan.html").render(**ansicht) if mit_html else None
    ansicht.pop("graph_json", None)
    modell = modell_3d(ergebnis)
    glb = usdz = None
    if mit_glb:  # dazu USDZ für die AR-Ansicht auf dem iPhone (das Möbel in echter Größe im Zimmer)
        glb = _url(await run_in_threadpool(speicher.bild_speichern, _db(e), k.geraet, als_glb(modell), "model/gltf-binary"))
        usdz = _url(await run_in_threadpool(speicher.bild_speichern, _db(e), k.geraet, als_usdz(modell),
                                            "model/vnd.usdz+zip")) + "/parawerk.usdz"
    return BauplanAntwort(name=graph["name"], offene_punkte=ergebnis.offene_punkte, bauplan=ansicht,
                          modell=modell, modell_glb=glb, modell_usdz=usdz, plan=ergebnis.plan, html=html)


def _dateiname(name: str) -> str:
    """Name des Möbels als einfacher Dateiname (nur Buchstaben, Ziffern, Bindestrich)."""
    ersetzt = name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    teile = re.findall(r"[a-z0-9]+", ersetzt)
    return "parawerk-" + ("-".join(teile)[:40] or "bauplan") + ".pdf"


@router.post("/bauplan/pdf", response_model=None)
async def pdf(anfrage: PdfV1, link: bool = False, k: Kunde = Depends(kunde),
              e: Einstellungen = Depends(einstellungen)) -> Response | dict:
    """Bauplan als PDF zum Herunterladen und Ausdrucken, mit Entwurf und 3D-Bild.

    ``link=true`` (für die App): das PDF wird gespeichert, die Antwort ist ``{"url": …}`` zum Öffnen und Teilen.
    """
    graph = _graph(anfrage.graph)
    ergebnis = await run_in_threadpool(_rechnen, graph, anfrage.bereich, anfrage.sortiment or e.sortiment)
    entwurf = None
    if anfrage.entwurf_id:
        gefunden = await run_in_threadpool(speicher.bild_laden, _db(e), anfrage.entwurf_id)
        if gefunden and gefunden[1].startswith("image/"):
            entwurf = ba.aus_bytes(gefunden[0])
    daten = await run_in_threadpool(bauplan_pdf, bauplan_ansicht(ergebnis, graph, anfrage.bereich), modell_3d(ergebnis), entwurf)
    name = _dateiname(graph["name"])
    await run_in_threadpool(analyse.eintragen, _db(e), "pdf", {
        "bereich": anfrage.bereich, "graph": graph, "masse": ergebnis.dims, "teile": len(ergebnis.members),
        "ergaenzt": sum(1 for m in ergebnis.members if m.origin == "reparatur"), "offene_punkte": ergebnis.offene_punkte,
        "einkauf": ergebnis.plan["lines"], "schnitte": ergebnis.plan["cuts"]},
        lauf_id=analyse.lauf(anfrage.maske_id), sprache=sprache(), demo=not e.claude_aktiv)
    if link:
        bid = await run_in_threadpool(speicher.bild_speichern, _db(e), k.geraet, daten, "application/pdf")
        return {"url": f"{_url(bid)}/{name}"}
    return Response(daten, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/analyse", include_in_schema=False)
async def analyse_export(art: str | None = None, demo: bool = False, k: Kunde = Depends(kunde),
                         e: Einstellungen = Depends(einstellungen)) -> list[dict]:
    """Anonyme Analyse-Daten als JSON, nur mit Admin-Schlüssel (``/?schluessel=…`` vorher im Browser)."""
    if not k.admin:
        raise HTTPException(404, "Not Found")
    return await run_in_threadpool(analyse.alle, _db(e), art, demo)


@router.post("/bauplan/dxf")
async def dxf(anfrage: BerechnenV1, e: Einstellungen = Depends(einstellungen)) -> Response:
    ergebnis = await run_in_threadpool(_rechnen, _graph(anfrage.graph), anfrage.bereich, anfrage.sortiment or e.sortiment)
    return Response(teile_als_dxf(ergebnis.members), media_type="application/dxf",
                    headers={"Content-Disposition": 'attachment; filename="parawerk.dxf"'})
