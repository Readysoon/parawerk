"""Bauplan als PDF: mit und ohne Entwurf, als Download und als Link für die App, in beiden Sprachen."""
from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.views.pdf import _sauber
from tests.hilfen import FOTO, MASKE, warten

GRAPHEN = json.loads((Path(__file__).parents[1] / "app/services/demo_graphen.json").read_text(encoding="utf-8"))
KOPF = {"X-Geraet": "pdf-test-0001"}


def test_pdf_download_mit_entwurf():
    with TestClient(app, headers=KOPF) as c:
        entwurf = warten(c, c.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE}), KOPF)["ergebnis"]["entwuerfe"][0]["id"]
        r = c.post("/api/v1/bauplan/pdf", json={"graph": GRAPHEN[3], "bereich": [2500, 1000, 1000], "entwurf_id": entwurf})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and r.content.count(b"/Subtype /Image") >= 2  # Entwurf und 3D-Bild
    assert 'filename="parawerk-gartenbank-mit-stablehne.pdf"' in r.headers["content-disposition"]


def test_pdf_als_link_englisch_und_gestreckt():
    with TestClient(app, headers={**KOPF, "X-Sprache": "en"}) as c:
        r = c.post("/api/v1/bauplan/pdf?link=true", json={"graph": {**GRAPHEN[1], "ziel": [1400, 330, 449]},
                                                          "bereich": [2500, 1000, 1000]})
        url = r.json()["url"]
        assert url.endswith("/parawerk-lattenbank.pdf")
        pdf = c.get(url)
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert b"/Subtype /Image" in pdf.content  # 3D-Bild auch ohne Entwurf


def test_zeichen_fuer_pdf_schrift():
    assert _sauber("ca. ≈ 3 → 4 × 5 € <b>") == "ca. ca. 3 -&gt; 4 × 5 € &lt;b&gt;"
    assert "?" in _sauber("日本")  # unbekannte Zeichen stören nicht


def _pdf_text(daten: bytes) -> bytes:
    """Seiteninhalte eines reportlab-PDFs (ASCII85 + Flate) als Rohtext, ohne zusätzliche Bibliothek."""
    import base64
    import re
    import zlib
    teile = re.findall(rb"/Filter \[ /ASCII85Decode /FlateDecode \][^>]*>>\s*stream\r?\n(.*?)endstream", daten, re.S)
    return b"".join(zlib.decompress(base64.a85decode(t.strip().removesuffix(b"~>"))) for t in teile)


def test_ohne_pruefung_im_pdf():
    with TestClient(app, headers=KOPF) as c:
        r = c.post("/api/v1/bauplan/pdf", json={"graph": GRAPHEN[0], "bereich": [2500, 1000, 1000]})
    text = _pdf_text(r.content)
    assert b"Einkaufsliste" in text and b"Montage" in text
    assert b"Pr\xfcfung" not in text and b"Faustregel" not in text  # Prüfungen sind intern
