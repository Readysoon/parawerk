"""Sicherheitsregeln: Hochbetten (EN 747) werden gesperrt, hohe Regale bekommen eine Kippsicherung."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.models.engine import berechnen, sicherheit
from app.models.engine.grundlagen import Bauteil


def _teil(rolle, z0, z1):
    return Bauteil(min=[0, 0, z0], max=[2000, 900, z1], long=0, rolle=rolle)


def test_hochbett_ab_600_mm():
    bein = Bauteil(min=[0, 0, 0], max=[60, 60, 1600], long=2, rolle="bein")
    assert sicherheit.ist_hochbett([bein, _teil("lattenrost", 1180, 1200)], {"kategorie": "bett"}) == 1200
    assert sicherheit.ist_hochbett([bein, _teil("lattenrost", 380, 400)], {"kategorie": "bett"}) is None
    assert sicherheit.ist_hochbett([bein, _teil("sitzflaeche", 700, 720)], {"kategorie": "bank"}) is None


def test_api_sperrt_hochbett(monkeypatch):
    from app.controllers import api_v1

    class E:
        members = [Bauteil(min=[0, 0, 0], max=[60, 60, 1600], long=2, rolle="bein"), _teil("liegeflaeche", 1300, 1320)]
    monkeypatch.setattr(api_v1, "engine_berechnen", lambda *a: E())
    with pytest.raises(HTTPException) as f:
        api_v1._rechnen({"kategorie": "bett"}, [2000, 1000, 2000], "DE")
    assert f.value.status_code == 422 and "1320" in f.value.detail


def test_hohes_regal_bekommt_kippsicherung():
    faelle = json.loads(gzip.open(Path(__file__).parent / "referenz" / "engine_faelle.json.gz", "rt").read())
    f = next(x for x in faelle if x["name"] == "fuzz39_blindtest2")
    e = berechnen(f["graph"], f["bereich"], f["sortiment"])
    assert any("Kippsicherung" in h["text"] for h in e.plan["hardware"])
    assert e.plan["steps"][-1]["key"] == "montage.kippsicherung"
    assert any("Kippsicherung" in c["t"] for c in e.checks)
    from app.models.engine.anleitung import anleitung
    a = anleitung(e.members, e.joints, e.plan, e.dims)
    assert "Kippsicherung" in a["schritte"][-1]["t"]


def test_niedriges_regal_und_wandregal_ohne():
    boden = Bauteil(min=[0, 0, 300], max=[800, 300, 318], long=0, rolle="regalboden")
    bein = Bauteil(min=[0, 0, 0], max=[30, 30, 500], long=2, rolle="bein")
    assert not sicherheit.braucht_kippsicherung([boden, bein], {"kategorie": "regal"})
    hoch = Bauteil(min=[0, 0, 0], max=[30, 30, 1800], long=2, rolle="bein")
    wand = Bauteil(min=[0, 280, 1500], max=[800, 300, 1560], long=0, rolle="wandleiste")
    assert sicherheit.braucht_kippsicherung([boden, hoch], {"kategorie": "regal"})
    assert not sicherheit.braucht_kippsicherung([boden, hoch, wand], {"kategorie": "regal"})
