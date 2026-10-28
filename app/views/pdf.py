"""Bauplan als PDF zum Herunterladen und Ausdrucken: Entwurf, 3D-Bild, Prüfung, Einkaufsliste, Montage, Zuschnitt.

Gebaut mit reportlab und den eingebauten PDF-Schriften (Helvetica). Die kennen nur den Windows-Zeichensatz
(Umlaute, ×, €, – ja; ≈, → nein), darum werden ein paar Zeichen vorher ersetzt.
"""
from __future__ import annotations

import io
from datetime import date

from PIL import Image
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image as PdfBild, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from xml.sax.saxutils import escape

from ..i18n import t
from ..models.ansicht import modellbild
from .praesentation import eur, meter

HOLZ = colors.HexColor("#d8c2a0")
ERGAENZT = colors.HexColor("#c2410c")
DUNKEL = colors.HexColor("#1c2530")
GRAU = colors.HexColor("#6b7480")
LINIE = colors.HexColor("#d5dae0")
FARBE_STATUS = {"ok": colors.HexColor("#2f7d4f"), "no": colors.HexColor("#a15c00"), "info": GRAU}

ERSATZ = {"≈": "ca.", "→": "->", "←": "<-", "≤": "<=", "≥": ">=", " ": " ", " ": " ", "‑": "-",
          "√": "Wurzel"}

BREITE = A4[0] - 36 * mm  # nutzbare Breite

_text = ParagraphStyle("text", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=DUNKEL)
_klein = ParagraphStyle("klein", parent=_text, fontSize=8, leading=10, textColor=GRAU)
_titel = ParagraphStyle("titel", parent=_text, fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
_h2 = ParagraphStyle("h2", parent=_text, fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=5)
_h3 = ParagraphStyle("h3", parent=_text, fontName="Helvetica-Bold", fontSize=9.5, spaceBefore=5, spaceAfter=2)


def _sauber(s: object) -> str:
    """Text für die eingebauten PDF-Schriften: unbekannte Zeichen ersetzen, dann für Paragraph maskieren."""
    s = str(s)
    for a, b in ERSATZ.items():
        s = s.replace(a, b)
    s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s)


def _p(s: object, stil: ParagraphStyle = _text) -> Paragraph:
    return Paragraph(_sauber(s), stil)


def _bild(img: Image.Image, breite: float) -> PdfBild:
    puffer = io.BytesIO()
    img.convert("RGB").save(puffer, "JPEG", quality=88)
    puffer.seek(0)
    return PdfBild(puffer, width=breite, height=breite * img.height / img.width)


def modell_als_bild(modell: dict) -> Image.Image:
    """3D-Bild des berechneten Möbels, doppelt so groß gezeichnet und verkleinert (glattere Kanten)."""
    gross = modellbild(modell, 2000, 1400)
    return gross.resize((1000, 700), Image.LANCZOS)


def _stange(stueck: list[dict], laenge: float, breite: float) -> Drawing:
    """Eine Stange als Balken mit ihren Zuschnitten (wie auf der Website)."""
    h = 13
    d = Drawing(breite, h + 2)
    d.add(Rect(0, 1, breite, h, fillColor=colors.HexColor("#eef0f2"), strokeColor=LINIE, strokeWidth=0.5))
    x = 0.0
    for p in stueck:
        w = breite * p["len"] / laenge
        d.add(Rect(x, 1, w, h, fillColor=ERGAENZT if p["ergaenzt"] else HOLZ, strokeColor=colors.white, strokeWidth=1))
        if w > 22:
            d.add(String(x + w / 2, 4.5, str(p["len"]), fontName="Helvetica", fontSize=7,
                         fillColor=colors.white if p["ergaenzt"] else DUNKEL, textAnchor="middle"))
        x += w
    return d


def _platte(teile: list[dict], seitenverhaeltnis: str, breite: float) -> Drawing:
    L, W = (float(v) for v in seitenverhaeltnis.split("/"))
    hoehe = breite * W / L
    d = Drawing(breite, hoehe + 2)
    d.add(Rect(0, 1, breite, hoehe, fillColor=colors.HexColor("#eef0f2"), strokeColor=LINIE, strokeWidth=0.5))
    for st in teile:
        x, y = float(st["links"][:-1]) / 100 * breite, float(st["oben"][:-1]) / 100 * hoehe
        w, h = float(st["breite"][:-1]) / 100 * breite, float(st["hoehe"][:-1]) / 100 * hoehe
        d.add(Rect(x, 1 + hoehe - y - h, w, h, fillColor=HOLZ, strokeColor=colors.white, strokeWidth=1))
        if w > 40 and h > 9:
            d.add(String(x + w / 2, 1 + hoehe - y - h / 2 - 2.5, f"{st['l']}×{st['w']}", fontName="Helvetica",
                         fontSize=7, fillColor=DUNKEL, textAnchor="middle"))
    return d


def _tabelle(zeilen: list[list], spalten: list[float], kopf: bool = True) -> Table:
    tab = Table(zeilen, colWidths=spalten, hAlign="LEFT")
    stil = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINIE),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if kopf:
        stil += [("LINEBELOW", (0, 0), (-1, 0), 0.8, DUNKEL)]
    tab.setStyle(TableStyle(stil))
    return tab


def bauplan_pdf(ansicht: dict, modell: dict, entwurf: Image.Image | None = None) -> bytes:
    """``ansicht`` wie ``bauplan_ansicht``, ``modell`` wie ``modell_3d``; ``entwurf`` = gewählter Entwurf (optional)."""
    puffer = io.BytesIO()
    titel = t("pdf.titel", name=ansicht["name"])

    def seite(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRAU)
        canvas.drawString(18 * mm, 10 * mm, _sauber(t("pdf.fuss", datum=date.today().strftime("%d.%m.%Y"))))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, _sauber(t("pdf.seite", n=doc.page)))
        canvas.setFillColor(colors.HexColor("#e8b400"))
        canvas.rect(18 * mm, A4[1] - 12 * mm, A4[0] - 36 * mm, 1.2 * mm, stroke=0, fill=1)
        canvas.restoreState()

    doc = SimpleDocTemplate(puffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=17 * mm,
                            bottomMargin=17 * mm, title=_sauber(titel), author="Parawerk")
    inhalt: list = [_p(titel, _titel)]
    status = t("bp.ok") if not ansicht["offene_punkte"] else (
        t("bp.punkt") if ansicht["offene_punkte"] == 1 else t("bp.punkte", n=ansicht["offene_punkte"]))
    inhalt.append(_p(f"{t('bp.aussenmass')}: {ansicht['aussenmass']} mm  ·  {ansicht['anzahl_teile']} "
                     f"{t('bp.einzelteile')}  ·  {status}", _klein))
    inhalt.append(Spacer(1, 6))

    # Bilder: Entwurf und 3D-Modell nebeneinander (ohne Entwurf das 3D-Modell groß)
    modell_img = modell_als_bild(modell)
    if entwurf is not None:
        halb = (BREITE - 6 * mm) / 2
        bilder = Table([[_bild(entwurf, halb), _bild(modell_img, halb)],
                        [_p(t("pdf.entwurf"), _klein), _p(t("pdf.modell"), _klein)]],
                       colWidths=[halb + 3 * mm, halb + 3 * mm], hAlign="LEFT")
        bilder.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        inhalt.append(bilder)
    else:
        inhalt += [_bild(modell_img, BREITE * 0.8), _p(t("pdf.modell"), _klein)]
    inhalt.append(Paragraph(f'<font color="#b89c74"><b>{_sauber(t("pdf.hell"))}</b></font> {_sauber(t("ui.leg_entwurf"))}'
                            f' &nbsp; <font color="#c2410c"><b>{_sauber(t("pdf.orange"))}</b></font> '
                            f'{_sauber(t("ui.leg_ergaenzt"))}', _klein))

    # Prüfung
    inhalt.append(_p(t("bp.pruefung"), _h2))
    zeilen = []
    for pr in ansicht["pruefungen"]:
        farbe = FARBE_STATUS.get(pr["klasse"], GRAU).hexval()[2:]
        zeilen.append([Paragraph(f'<font color="#{farbe}"><b>{_sauber(pr["status"])}</b></font>', _text), _p(pr["text"])])
    inhalt.append(_tabelle(zeilen, [20 * mm, BREITE - 20 * mm], kopf=False))

    # Einkaufsliste
    zeilen = [[_p(t("bp.menge")), _p(t("bp.artikel"))]]
    zeilen += [[_p(f"{l['n']}×"), _p(l["text"])] for l in ansicht["einkauf"]]
    zeilen += [[_p(l["n"]), _p(f"{l['text']} {t('bp.reserve')}")] for l in ansicht["beschlaege"]]
    inhalt.append(KeepTogether([_p(t("bp.einkauf"), _h2), _tabelle(zeilen, [18 * mm, BREITE - 18 * mm]),
                                Spacer(1, 3), _p(t("bp.zuschnitt_markt", n=ansicht["schnitte"], preis=eur(0.99),
                                                   kosten=eur(ansicht["schnittkosten"])), _klein)]))

    # Montage
    punkte = [ListItem(_p(f"{s['t']} ({t('bp.teile', n=s['n']).strip('()')})"), leftIndent=12)
              for s in ansicht["montage"]]
    inhalt += [_p(t("bp.montage"), _h2), ListFlowable(punkte, bulletType="1", bulletFontName="Helvetica", bulletFontSize=9.5,
                                                        leftIndent=14)]

    # Zuschnittplan
    inhalt.append(_p(t("bp.zuschnittplan"), _h2))
    for g in ansicht["zuschnitt"]:
        teil: list = [_p(g["label"], _h3)]
        if g["art"] == "stab":
            for s in g["stangen"]:
                kopf = t("bp.stange", n=s["anzahl"], m=meter(s["laenge"])) + (t("bp.zu_lang") if s["zu_lang"] else "")
                zeile = Table([[_p(kopf, _klein), Paragraph(_sauber(t("bp.rest", n=s["rest"])),
                                                              ParagraphStyle("r", parent=_klein, alignment=2))]],
                              colWidths=[BREITE * 0.7, BREITE * 0.3])
                zeile.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
                teil += [zeile, _stange(s["stuecke"], s["laenge"], BREITE)]
        else:
            for platte in g["platten"]:
                teil += [_platte(platte, g["seitenverhaeltnis"], BREITE * 0.75), Spacer(1, 4)]
        inhalt.append(KeepTogether(teil))
    inhalt += [Spacer(1, 4), _p(t("bp.orange"), _klein)]

    doc.build(inhalt, onFirstPage=seite, onLaterPages=seite)
    return puffer.getvalue()
