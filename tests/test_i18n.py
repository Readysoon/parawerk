"""Zweisprachigkeit: Kataloge vollständig, Sprache aus URL, Cookie und Browser, englische Ausgabe ohne deutsche Reste."""
import re
import string

import pytest
from fastapi.testclient import TestClient

from app.i18n import KATALOG, aus_header, holz, in_sprache, t
from app.main import app

BEREICH = [1800, 900, 900]


def _platzhalter(text: str) -> set[str]:
    return {f[1] for f in string.Formatter().parse(text) if f[1]}


def test_kataloge_gleich_aufgebaut():
    de, en = KATALOG["de"], KATALOG["en"]
    assert not [k for k in de if k not in en]
    assert not [k for k in de if _platzhalter(de[k]) != _platzhalter(en[k])]


def test_sprache_bestimmen():
    assert aus_header("en-US,en;q=0.9,de;q=0.8") == "en"
    assert aus_header("fr-FR,de;q=0.5") == "de"
    assert aus_header(None) == "de"
    with in_sprache("en"):
        assert t("bp.ok") == "buildable and stable" and holz("Latte 24×44 gehobelt") == "Planed batten 24×44"
    assert t("bp.ok") == "baubar und stabil"


def test_seite_folgt_browser_und_umschalter():
    c = TestClient(app)
    assert '<html lang="de"' in c.get("/").text
    assert '<html lang="en"' in c.get("/", headers={"accept-language": "en-GB"}).text
    r = c.get("/?sprache=en", headers={"accept-language": "de"})
    assert '<html lang="en"' in r.text and "sprache=en" in r.headers["set-cookie"]
    assert '<html lang="en"' in c.get("/", headers={"accept-language": "de"}).text  # Cookie gewinnt


@pytest.mark.parametrize("i", range(4))
def test_bauplan_englisch(i):
    c = TestClient(app, cookies={"sprache": "en"})
    graph = c.post("/api/bauplan/lesen", json={"bereich": BEREICH, "demo_index": i}).json()["graph"]
    assert not re.search(r"[äöüß]", graph["name"] + "".join(teil["name"] for teil in graph["teile"]))
    j = c.post("/api/bauplan/berechnen", json={"graph": graph, "bereich": BEREICH}).json()
    text = re.sub(r"<[^>]+>", " ", re.sub(r'<pre class="graph">.*?</pre>', "", j["html"], flags=re.S))
    assert "Shopping list" in text and "Cut plan" in text
    for wort in ("Einkaufsliste", "Stange", "Prüfung", "Latte", "Leimholz", "Rahmenholz", "Holzschraube", "Teile"):
        assert wort not in text


def test_fehler_englisch():
    c = TestClient(app, headers={"x-sprache": "en"})
    assert c.post("/api/bauplan/berechnen", json={"graph": {"teile": []}, "bereich": BEREICH}).json() == {
        "fehler": "The part graph has no parts."}
    assert c.post("/api/bauplan/berechnen", json={}).json()["fehler"].startswith("Invalid input:")
    graph = c.post("/api/bauplan/lesen", json={"bereich": BEREICH}).json()["graph"]
    r = c.post("/api/bauplan/anpassen", json={"graph": graph, "wunsch": "wider"})
    assert r.status_code == 501 and r.json()["fehler"].startswith("Adjusting by text")
