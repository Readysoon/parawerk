"""Datenschutzerklärung als Seite; Schriften vom eigenen Server (keine IP-Adressen an Google Fonts)."""
from fastapi.testclient import TestClient

from app.main import app


def test_datenschutz_seite_und_keine_fremden_schriften():
    with TestClient(app) as c:
        seite = c.get("/datenschutz")
        start = c.get("/")
        css = c.get("/static/css/schriften.css")
        schrift = c.get("/static/schriften/ibm-plex-sans-latin-400-normal.woff2")
    assert seite.status_code == 200 and "Datenschutzerklärung" in seite.text and "<table>" in seite.text
    assert 'href="/datenschutz"' in start.text
    for html in (seite.text, start.text):
        assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert css.status_code == 200 and "/static/schriften/" in css.text and "gstatic" not in css.text
    assert schrift.status_code == 200 and len(schrift.content) > 1000
