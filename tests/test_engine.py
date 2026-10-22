"""Engine: gleiche Ergebnisse wie die ursprüngliche JS-Engine, und die Demo-Möbel sind baubar und stabil."""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import pytest

from app.models.dxf import teile_als_dxf
from app.models.engine import berechnen
from app.services.konstrukteur import demo_graphen

REFERENZ = Path(__file__).parent / "referenz" / "js_engine_faelle.json.gz"
FAELLE = json.loads(gzip.open(REFERENZ, "rt", encoding="utf-8").read())


def _abweichung(a, b, pfad=""):
    """Erste Abweichung zweier JSON-Strukturen (Zahlen mit 1e-6 Toleranz) oder None."""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a == b else f"{pfad}: {a!r} != {b!r}"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return None if math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6) else f"{pfad}: {a!r} != {b!r}"
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() | b.keys():
            if k not in a or k not in b:
                return f"{pfad}.{k} fehlt"
            if r := _abweichung(a[k], b[k], f"{pfad}.{k}"):
                return r
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{pfad}: {len(a)} statt {len(b)} Einträge"
        for i, (x, y) in enumerate(zip(a, b)):
            if r := _abweichung(x, y, f"{pfad}[{i}]"):
                return r
        return None
    return None if a == b else f"{pfad}: {a!r} != {b!r}"


@pytest.mark.parametrize("fall", FAELLE, ids=[f["name"] for f in FAELLE])
def test_gleich_wie_js_engine(fall):
    r = berechnen(fall["graph"], fall["bereich"], fall["sortiment"]).als_dict()
    assert _abweichung(json.loads(json.dumps(r)), fall["erwartet"]) is None


@pytest.mark.parametrize("i", range(4))
def test_demo_moebel_baubar_und_stabil(i):
    e = berechnen(demo_graphen()[i], [2500, 2200, 1300])
    assert e.offene_punkte == 0, [c["t"] for c in e.checks if c["ok"] is False]
    assert all(m.max[a] > m.min[a] for m in e.members for a in range(3))
    assert e.plan["lines"] and e.plan["cuts"] > 0


def test_daybed_masse():
    e = berechnen(demo_graphen()[3], [2200, 1000, 1000])
    assert e.dims == [1750, 854, 563]


def test_zu_kleiner_bereich_wird_gemeldet():
    e = berechnen(demo_graphen()[3], [1000, 600, 400])
    bereich = e.checks[-1]
    assert bereich["ok"] is False and "passt nicht" in bereich["t"]


def test_eingabe_bleibt_unveraendert():
    g = demo_graphen()[1]
    vorher = json.dumps(g)
    berechnen(g, [2500, 2000, 1200], "US")
    assert json.dumps(g) == vorher


def test_dxf():
    e = berechnen(demo_graphen()[0], [2200, 1000, 1000])
    dxf = teile_als_dxf(e.members)
    assert dxf.startswith("0\nSECTION") and dxf.endswith("EOF")
    assert dxf.count("\nLINE\n") == 4 * len(e.members)
