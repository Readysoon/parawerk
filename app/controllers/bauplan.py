"""Bauplan-Controller: Entwurf lesen, per Text anpassen, berechnen, als DXF ausgeben."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..models.bauteilgraph import GraphFehler, bereinigen
from ..models.dxf import teile_als_dxf
from ..models.engine import Ergebnis, berechnen
from ..services.fehler import DienstFehler, NichtVerfuegbar
from ..services.konstrukteur import Konstrukteur
from ..services.kostendeckel import Kostendeckel, Kunde
from ..views import templates
from ..views.praesentation import bauplan_ansicht, modell_3d
from .abhaengigkeiten import konstrukteur, kostendeckel, kunde
from .kontingent import erstatten, reservieren
from .schemas import AnpassenAnfrage, BerechnenAnfrage, GraphAntwort, LesenAnfrage

router = APIRouter(prefix="/api/bauplan", tags=["Bauplan"])


@router.post("/lesen", response_model=GraphAntwort)
async def lesen(anfrage: LesenAnfrage, k: Konstrukteur = Depends(konstrukteur),
                deckel: Kostendeckel = Depends(kostendeckel), kd: Kunde = Depends(kunde)) -> GraphAntwort:
    """Konstruktion (Bauteilgraph) aus dem Ausschnitt des gewählten Entwurfs lesen."""
    if not k.demo and not anfrage.bild:
        raise HTTPException(400, t("fehler.ausschnitt"))
    eintrag = None if k.demo else await reservieren(deckel, "lesen", kd)
    try:
        graph = await k.lesen(anfrage.bild, anfrage.bereich, anfrage.demo_index)
    except (DienstFehler, GraphFehler) as err:
        await erstatten(deckel, eintrag)
        raise HTTPException(502, t("fehler.lesen", err=err)) from err
    return GraphAntwort(demo=k.demo, graph=graph)


@router.post("/anpassen", response_model=GraphAntwort)
async def anpassen(anfrage: AnpassenAnfrage, k: Konstrukteur = Depends(konstrukteur),
                   deckel: Kostendeckel = Depends(kostendeckel), kd: Kunde = Depends(kunde)) -> GraphAntwort:
    """Bauteilgraph nach einem Wunsch in Worten ändern."""
    graph = _graph(anfrage.graph)
    eintrag = None if k.demo else await reservieren(deckel, "anpassen", kd)
    try:
        graph = await k.anpassen(graph, anfrage.wunsch)
    except NichtVerfuegbar as err:
        raise HTTPException(501, str(err)) from err
    except (DienstFehler, GraphFehler) as err:
        await erstatten(deckel, eintrag)
        raise HTTPException(502, t("fehler.aenderung", err=err)) from err
    return GraphAntwort(demo=k.demo, graph=graph)


@router.post("/berechnen")
def berechnen_route(anfrage: BerechnenAnfrage, e: Einstellungen = Depends(einstellungen)) -> dict:
    """Bauteilgraph → baubares Modell. Liefert den Bauplan als HTML-Ausschnitt und das Modell für die 3D-Ansicht."""
    graph = _graph(anfrage.graph)
    ergebnis = _rechnen(graph, anfrage.bereich, anfrage.sortiment or e.sortiment)
    ansicht = bauplan_ansicht(ergebnis, graph, anfrage.bereich)
    return {
        "name": graph["name"],
        "offene_punkte": ergebnis.offene_punkte,
        "html": templates.get_template("teile/bauplan.html").render(**ansicht),
        "modell": modell_3d(ergebnis),
        "plan": ergebnis.plan,
    }


@router.post("/dxf")
def dxf(anfrage: BerechnenAnfrage, e: Einstellungen = Depends(einstellungen)) -> Response:
    """Alle Zuschnitte als DXF-Zeichnung."""
    ergebnis = _rechnen(_graph(anfrage.graph), anfrage.bereich, anfrage.sortiment or e.sortiment)
    return Response(teile_als_dxf(ergebnis.members), media_type="application/dxf",
                    headers={"Content-Disposition": 'attachment; filename="parawerk.dxf"'})


def _graph(roh: dict) -> dict:
    try:
        return bereinigen(roh)
    except GraphFehler as err:
        raise HTTPException(422, str(err)) from err


def _rechnen(graph: dict, bereich: list[float], sortiment: str) -> Ergebnis:
    try:
        return berechnen(graph, bereich, sortiment)
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as err:
        raise HTTPException(422, t("fehler.modell", art=type(err).__name__)) from err
