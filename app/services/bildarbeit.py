"""Bildarbeit am Server für die App: Entwurf ins Foto einsetzen und Ausschnitt fürs Lesen.

Dasselbe, was die Website in ``app.js`` im Browser macht (``einsetzen``, ``bauplanErstellen``), damit die
Flutter-App nur fotografieren, malen und anzeigen muss.
"""
from __future__ import annotations

import base64
import io
import re

from PIL import Image, ImageFilter, ImageOps

from ..i18n import t
from .fehler import DienstFehler

MAXPX = 1024  # wie im Browser: lange Seite höchstens 1024 px
DATA_URL = re.compile(r"^data:(image/[a-z]+);base64,(.*)$", re.S)


def aus_data_url(url: str) -> Image.Image:
    m = DATA_URL.match(url or "")
    if not m:
        raise DienstFehler(t("fehler.data_url"))
    try:
        bild = Image.open(io.BytesIO(base64.b64decode(m.group(2))))
        bild.load()
    except Exception as err:  # beschädigtes oder unbekanntes Bildformat
        raise DienstFehler(t("fehler.bild_kaputt")) from err
    return bild


def aus_bytes(daten: bytes) -> Image.Image:
    bild = Image.open(io.BytesIO(daten))
    bild.load()
    return bild


def jpeg(bild: Image.Image, qualitaet: int = 88) -> bytes:
    puffer = io.BytesIO()
    bild.convert("RGB").save(puffer, "JPEG", quality=qualitaet)
    return puffer.getvalue()


def png(bild: Image.Image) -> bytes:
    puffer = io.BytesIO()
    bild.save(puffer, "PNG")
    return puffer.getvalue()


def als_data_url(daten: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(daten).decode()}"


def foto_vorbereiten(bild: Image.Image) -> Image.Image:
    """Foto auf höchstens 1024 px verkleinern, Ausrichtung aus EXIF übernehmen."""
    bild = ImageOps.exif_transpose(bild).convert("RGB")
    s = min(1.0, MAXPX / max(bild.size))
    return bild.resize((round(bild.width * s), round(bild.height * s)), Image.LANCZOS) if s < 1 else bild


def maske_vorbereiten(maske: Image.Image, groesse: tuple[int, int]) -> Image.Image:
    """Maske als Graustufen in Fotogröße: weiß = hier wird gemalt. Bei transparenten PNGs zählt der Alphakanal."""
    alpha = maske.convert("RGBA").getchannel("A") if maske.mode in ("RGBA", "LA", "PA") or "transparency" in maske.info else None
    if alpha is not None and alpha.getextrema()[0] < 255:
        maske = alpha  # Mal-Ebene: was deckend gemalt ist, zählt, egal in welcher Farbe
    else:
        maske = maske.convert("L")
    return maske.resize(groesse, Image.BILINEAR) if maske.size != groesse else maske


def ki_maske(maske: Image.Image) -> Image.Image:
    """Maske für die Bild-KI: leicht weichgezeichnet, wie im Browser."""
    return maske.filter(ImageFilter.GaussianBlur(2))


def rahmen(maske: Image.Image) -> tuple[int, int, int, int] | None:
    """Umgebendes Rechteck der markierten Fläche (x0, y0, x1, y1) oder None, wenn nichts markiert ist."""
    return maske.point(lambda v: 255 if v > 10 else 0).getbbox()


def einsetzen(foto: Image.Image, maske: Image.Image, entwurf: Image.Image) -> Image.Image:
    """Nur den markierten Bereich (weich ausgeblendet) aus dem Entwurf ins Originalfoto übernehmen."""
    weich = maske.filter(ImageFilter.GaussianBlur(10))
    weich = Image.eval(weich, lambda v: min(255, v * 2))  # wie zweimal übereinander gezeichnet
    return Image.composite(entwurf.convert("RGB").resize(foto.size, Image.LANCZOS), foto.convert("RGB"), weich)


def ausschnitt(entwurf: Image.Image, maske: Image.Image) -> Image.Image:
    """Markierten Bereich plus 20 % Rand: Das bekommt Claude zum Lesen der Konstruktion."""
    r = rahmen(maske)
    if not r:
        return entwurf
    x0, y0, x1, y1 = r
    mx, my = (x1 - x0) * 0.2, (y1 - y0) * 0.2
    return entwurf.crop((max(0, round(x0 - mx)), max(0, round(y0 - my)),
                         min(entwurf.width, round(x1 + mx)), min(entwurf.height, round(y1 + my))))
