"""Statik (Vorbemessung nach Eurocode 5, Lasten nach Möbelnormen), stärkeres Holz bei Bedarf, Regeln fürs Strecken."""
from __future__ import annotations

from collections import Counter

import pytest

from app.models.bauteilgraph import bereinigen
from app.models.engine import berechnen
from app.models.engine.grundlagen import Bauteil
from app.models.engine.statik import _balken, _kippen, _knicken, grenz_spannweite

PLATZ = [6000, 3000, 3000]


def _latte(L: float, b: float = 44, h: float = 24, rolle: str = "sitzflaeche", z: float = 400) -> Bauteil:
    return Bauteil(id="t", part="t", name="Latte", typ="latte", rolle=rolle, prof={"label": "Latte"}, long=0, dax=-1,
                   origin="entwurf", min=[0, 0, z - h], max=[L, b, z])


def test_biegung_wie_von_hand():
    # Latte 44 breit, 24 hoch, 700 mm frei, 390 N auf 300 mm Länge in der Mitte:
    # M = 390·(2·700 − 300)/8 = 53 625 Nmm, W = 44·24²/6 = 4224 mm³, σ = 12,70 N/mm², f_m,d = 0,9·24/1,3 = 16,62,
    # Höhenbeiwert k_h = min((150/24)^0,2; 1,3) = 1,3 (kleine Querschnitte sind fester)
    n = _balken(_latte(700), 700, False, P=390)
    assert n.werte["M"] == 53625
    assert n.werte["biegung"] == pytest.approx(12.695 / (1.3 * 16.615), abs=0.002)


def test_kragarm_ist_kritischer():
    m = _latte(700)
    assert _balken(m, 400, True, P=390).werte["biegung"] > 2 * _balken(m, 400, False, P=390).werte["biegung"]


def test_knicken_schlanker_stab():
    bein = Bauteil(id="b", part="b", name="Bein", typ="kantholz", rolle="bein", prof={}, long=2, dax=-1, origin="entwurf",
                   min=[0, 0, 0], max=[44, 44, 2000])
    kurz = Bauteil(**{**bein.__dict__, "max": [44, 44, 400]})
    assert _knicken(bein, 5000).werte["kc"] < _knicken(kurz, 5000).werte["kc"] <= 1


def _bank(breite: float, sitz_vorne: float) -> list[Bauteil]:
    """Sitzfläche auf zwei Bodenkufen; ``sitz_vorne`` < 0: Sitz steht vorne über die Kufen hinaus."""
    def teil(id_, rolle, mn, mx):
        return Bauteil(id=id_, part=id_, name=id_, typ="kantholz", rolle=rolle, prof={}, long=0, dax=-1,
                       origin="entwurf", min=mn, max=mx)
    return [teil("kufe1", "kufe", [0, 0, 0], [breite, 44, 44]), teil("kufe2", "kufe", [0, 400, 0], [breite, 444, 44]),
            teil("sitz", "sitzflaeche", [0, sitz_vorne, 400], [breite, 444, 428])]


def test_kippen_nach_en_1022():
    assert _kippen(_bank(1000, 0), [_bank(1000, 0)[2]])["ausnutzung"] < 1
    weit_vorne = _bank(1000, -300)
    k = _kippen(weit_vorne, [weit_vorne[2]])
    assert k["ausnutzung"] > 1 and k["richtung"] == "vorne"


def test_regalboden_grenzspannweite_plausibel():
    boden = _latte(900, b=300, h=18, rolle="regalboden", z=1000)
    L = grenz_spannweite(boden, [boden], [], {"kategorie": "regal", "funktion": {}})
    assert 500 < L < 1200  # 18-mm-Fichte: übliche Regalböden spannen 60–90 cm


SITZBANK = {
    "name": "Testbank", "kategorie": "bank", "masse": {"breite": 1100, "tiefe": 400, "hoehe": 450},
    "funktion": {"sitzhoehe": 450, "polster": 0}, "anker": {"sitz_oben": 1.0},
    "teile": [
        {"id": "bein", "name": "Beine", "typ": "kantholz", "rolle": "bein", "box": [0, 1, 0, 1, 0, 0.94], "anzahl": 2,
         "achse": "x", "querschnitt": [44, 400]},
        {"id": "zarge", "name": "Seitenzargen", "typ": "kantholz", "rolle": "zarge", "box": [0, 1, 0, 1, 0.78, 0.94],
         "anzahl": 2, "achse": "x", "querschnitt": [44, 74]},
        {"id": "sitz", "name": "Sitzbrett", "typ": "brett", "rolle": "sitzflaeche", "box": [0, 1, 0, 1, 0.96, 1],
         "querschnitt": [18, 400]},
    ],
}


def test_billigere_loesung_wird_gewaehlt():
    """Sitzbrett 18 mm, 97 cm frei: 28-mm-Brett (≈ 4,4 l Holz mehr) oder eine Stütze (≈ 0,8 l)? Weniger Holz gewinnt."""
    from app.models.engine.reparatur import kontakte, spannweite, staerker_machen
    from app.models.sortiment import SORTIMENT_DE
    e = berechnen(bereinigen(SITZBANK), PLATZ)
    assert any("Stütze" in r for r in e.repairs) and not any("Stattdessen" in r for r in e.repairs)
    brett = next(m for m in e.members if m.part == "sitz")
    assert brett.prof["t"] == 18
    # die andere Lösung hätte mehr Holz gebraucht
    ohne_stuetze = [m for m in e.members if m.rolle != "stuetze"]
    J = kontakte(ohne_stuetze)
    laenge = spannweite(brett, J)["worst"]["len"]
    mehr = staerker_machen(SORTIMENT_DE, ohne_stuetze, brett, laenge, J, bereinigen(SITZBANK), nur_volumen=True)
    assert mehr is not None and mehr > 44 * 44 * 424


def test_regeln_fuers_strecken():
    g = bereinigen({**SITZBANK, "teile": [
        *SITZBANK["teile"][:2],
        {**SITZBANK["teile"][2], "anzahl": 4, "reihe": "anzahl"},  # Anzahl bleibt fest
        {"id": "brett", "name": "Ablage", "typ": "brett", "rolle": "regalboden", "box": [0.1, 0.3, 0.1, 0.9, 0.3, 0.34],
         "lage": {"x": "anfang", "y": "nix"}},
    ]})
    assert g["teile"][3]["lage"] == {"x": "anfang"} and g["teile"][2]["reihe"] == "anzahl"
    basis = berechnen(g, PLATZ)
    breit = berechnen({**g, "ziel": [2200, basis.dims[1], basis.dims[2]]}, PLATZ)
    assert Counter(m.part for m in breit.members)["sitz"] == 4
    ablage = lambda e: next(m for m in e.members if m.part == "brett")  # noqa: E731
    assert ablage(breit).max[0] - ablage(breit).min[0] == pytest.approx(ablage(basis).max[0] - ablage(basis).min[0], abs=2)


def test_sparsam_versteckte_teile():
    """Gartenbank mit Armlehnen: Zargen tragen wenig, werden schlanker; sichtbare Teile bleiben wie im Entwurf."""
    import json
    from pathlib import Path

    import app.models.engine as engine
    g = json.loads((Path(__file__).parents[1] / "app/services/demo_graphen.json").read_text(encoding="utf-8"))[0]

    def holz(e):
        return sum((m.max[0] - m.min[0]) * (m.max[1] - m.min[1]) * (m.max[2] - m.min[2]) for m in e.members)

    sparsam = berechnen(bereinigen(g), PLATZ)
    original, engine._sparen = engine._sparen, lambda S, gg, out, r: out
    try:
        voll = berechnen(bereinigen(g), PLATZ)
    finally:
        engine._sparen = original
    assert holz(sparsam) < holz(voll) and sparsam.offene_punkte == voll.offene_punkte == 0
    assert any("spart Holz" in r for r in sparsam.repairs)
    sichtbar = lambda e: {m.part: m.prof for m in e.members if m.rolle in ("bein", "pfosten", "lehne", "sitzflaeche")}  # noqa: E731
    assert sichtbar(sparsam) == sichtbar(voll)
    assert sparsam.fc["statik"].schlechtester.ausnutzung <= 1
