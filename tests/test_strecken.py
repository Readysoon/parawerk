"""Strecken und Stauchen: Design bleibt, Holzstärken bleiben, Reihen behalten ihren Abstand."""
from __future__ import annotations

from collections import Counter

import pytest

from app.models.bauteilgraph import bereinigen
from app.models.engine import berechnen
from tests.hilfen import alte_graphen

PLATZ = [6000, 3000, 3000]


def _mit_ziel(i: int, ziel) -> dict:
    g = bereinigen(alte_graphen()[i])
    g["ziel"] = ziel
    return bereinigen(g)


def _profile(e) -> dict:
    return {m.part: m.prof.get("label") or m.prof.get("t") for m in e.members if m.origin == "entwurf"}


@pytest.mark.parametrize("i", range(4))
def test_ohne_aenderung_gleich(i):
    basis = berechnen(bereinigen(alte_graphen()[i]), PLATZ)
    gleich = berechnen(_mit_ziel(i, basis.dims), PLATZ)
    # bis auf wenige mm (Rundung, Polster und Kontakte rechnen ab dem gebauten Maß noch einmal nach)
    assert all(abs(a - b) <= 10 for a, b in zip(gleich.dims, basis.dims)), (gleich.dims, basis.dims)
    assert len(gleich.members) == len(basis.members)


def test_bank_doppelt_so_breit():
    basis = berechnen(bereinigen(alte_graphen()[2]), PLATZ)  # Lattenbank 1500 breit, 16 Lehnenstäbe
    breit = berechnen(_mit_ziel(2, [3000, basis.dims[1], basis.dims[2]]), PLATZ)
    assert breit.dims == [3000, basis.dims[1], basis.dims[2]]
    alt, neu = Counter(m.part for m in basis.members), Counter(m.part for m in breit.members)
    assert neu["staebe"] >= 2 * alt["staebe"] - 2  # Abstand bleibt: etwa doppelt so viele Stäbe
    assert neu["sitz"] == alt["sitz"]  # Sitzbretter liegen in der Tiefe nebeneinander: bleiben 4, werden länger
    assert neu["beine-v"] == 2  # ein Beinpaar bleibt ein Paar; Stützen setzt die Reparatur
    assert _profile(breit) == _profile(basis)  # gleiche Holzstärken
    assert breit.offene_punkte == 0, [c["t"] for c in breit.checks if c["ok"] is False]
    assert any("Querriegel" in r and "×" in r for r in breit.repairs)  # mehrere Stege bei langer Spannweite


def test_schmaler_weniger_staebe_ohne_kollision():
    basis = berechnen(bereinigen(alte_graphen()[2]), PLATZ)
    schmal = berechnen(_mit_ziel(2, [900, basis.dims[1], basis.dims[2]]), PLATZ)
    assert schmal.dims == [900, basis.dims[1], basis.dims[2]]  # Tiefe bleibt (keine Teile verrutscht)
    assert Counter(m.part for m in schmal.members)["staebe"] < 16
    assert schmal.offene_punkte == 0


def test_sofa_hoeher():
    basis = berechnen(bereinigen(alte_graphen()[0]), PLATZ)
    hoch = berechnen(_mit_ziel(0, [basis.dims[0], basis.dims[1], 900]), PLATZ)
    assert abs(hoch.dims[2] - 900) <= 10
    assert hoch.offene_punkte == 0


def test_bett_springt_auf_matratzengroesse():
    basis = berechnen(bereinigen(alte_graphen()[1]), PLATZ)  # Matratze 1400 × 2000
    breiter = berechnen(_mit_ziel(1, [basis.dims[0], basis.dims[1] + 230, basis.dims[2]]), PLATZ)
    assert breiter.graph.get("ziel") and breiter.dims[1] > basis.dims[1]
    assert any("1600 × 2000" in z for z in breiter.steps[0]["log"])


def test_ziel_wird_geprueft():
    g = bereinigen({**alte_graphen()[0], "ziel": [10, 99999, "x"]})
    assert "ziel" not in g
    g = bereinigen({**alte_graphen()[0], "ziel": [10, 99999, 800]})
    assert g["ziel"] == [200, 6000, 800]


def test_api_mit_ziel_und_schnell():
    from fastapi.testclient import TestClient

    from app.main import app
    g = bereinigen(alte_graphen()[2])
    with TestClient(app, headers={"X-Geraet": "strecken-test-01"}) as c:
        for schnell in ("true", "false"):
            r = c.post(f"/api/v1/bauplan/berechnen?mit_glb=false&schnell={schnell}",
                       json={"graph": {**g, "ziel": [2400, 450, 804]}, "bereich": PLATZ})
            assert r.status_code == 200, r.text
            assert r.json()["modell"]["dims"][0] == 2400
