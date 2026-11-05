"""Bauplan als PDF zum Herunterladen und Ausdrucken: Entwurf, 3D-Bild, Einkaufsliste, Montage, Zuschnitt.

Die Prüfungen der Engine stehen bewusst nicht drin: Sie sind für uns, nicht für den Kunden.

Gebaut mit reportlab und den eingebauten PDF-Schriften (Helvetica). Die kennen nur den Windows-Zeichensatz
(Umlaute, ×, €, – ja; ≈, → nein), darum werden ein paar Zeichen vorher ersetzt.
"""
from __future__ import annotations

import io
from datetime import date
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image as PdfBild
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..i18n import dez, t
from ..models.ansicht import modellbild
from .praesentation import eur, meter

HOLZ = colors.HexColor("#d8c2a0")
ERGAENZT = colors.HexColor("#c2410c")
DUNKEL = colors.HexColor("#1c2530")
GRAU = colors.HexColor("#6b7480")
LINIE = colors.HexColor("#d5dae0")
ORANGE = colors.HexColor("#ec8024")
BEIGE = colors.HexColor("#f4f1ea")

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
        d.add(Rect(x, 1, w, h, fillColor=HOLZ, strokeColor=colors.white, strokeWidth=1))
        if w > 22:
            d.add(String(x + w / 2, 4.5, (f"{p['b']}  " if p.get("b") and w > 34 else "") + str(p["len"]),
                         fontName="Helvetica", fontSize=7,
                         fillColor=DUNKEL, textAnchor="middle"))
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
            d.add(String(x + w / 2, 1 + hoehe - y - h / 2 - 2.5,
                         (f"{st['b']}  " if st.get("b") else "") + f"{st['l']}×{st['w']}", fontName="Helvetica",
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


def _kopf(kopf: dict) -> Table:
    """Schwierigkeit, Bauzeit, Personen, Material: das Wichtigste auf einen Blick (wie bei guten Baumarkt-Anleitungen)."""
    wert = ParagraphStyle("w", parent=_text, fontName="Helvetica-Bold", fontSize=12, leading=15)
    punkte = Drawing(70, 14)  # fünf Punkte, gefüllt bis zur Schwierigkeit
    for i in range(5):
        punkte.add(Circle(6 + i * 13, 7, 5, fillColor=ORANGE if i < kopf["stufe"] else colors.white,
                          strokeColor=ORANGE, strokeWidth=1.2))
    felder = [(t("pdf.schwierigkeit"), punkte), (t("pdf.bauzeit"), _p(t("pdf.bauzeit_wert", h=dez(f"{kopf['stunden']:g}")), wert)),
              (t("pdf.personen"), _p(str(kopf["personen"]), wert))]
    if kopf.get("preis_text"):
        felder.append((t("pdf.material"), _p(t("pdf.material_wert", preis=kopf["preis_text"]), wert)))
    breite = BREITE / len(felder)
    tab = Table([[_p(k, _klein) for k, _ in felder], [v for _, v in felder]], colWidths=[breite] * len(felder),
                hAlign="LEFT")
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BEIGE),
                             ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.white),
                             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                             ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
    return tab


def _kaestchen() -> Drawing:
    d = Drawing(10, 10)
    d.add(Rect(1, 0, 9, 9, fillColor=colors.white, strokeColor=GRAU, strokeWidth=0.8))
    return d


def _schrittbild(modell: dict, ids: list[str], vorher: set[str], breite: int = 1500, hoehe: int = 1000) -> Image.Image:
    """Modell bis zu diesem Schritt: neue Teile orange mit Buchstaben, fertige Teile blass, spätere fehlen."""
    teile = [{**x, "stil": "neu" if x.get("id") in ids else "blass"} for x in modell["teile"]
             if x.get("id") in ids or x.get("id") in vorher]
    gross = modellbild({"teile": teile}, breite * 2, hoehe * 2, rahmen=modell, beschriften="neu",
                       hintergrund=(255, 255, 255))
    return gross.resize((breite, hoehe), Image.LANCZOS)


def _brauchst(s: dict) -> list:
    zeilen = []
    if s["teile"]:
        zeilen.append(_p("  ".join(f"{x['n']}× {x['b']}" for x in sorted(s["teile"], key=lambda x: (len(x["b"]), x["b"]))),
                         ParagraphStyle("tb", parent=_text, fontName="Helvetica-Bold")))
    if s.get("gurte"):
        zeilen.append(_p(t("pdf.gurte_n", n=s["gurte"])))
    zeilen += [_p(f"{x['n']}× {x['text']}") for x in s["schrauben"]]
    zeilen += [_p(w, _klein) for w in s["werkzeug"]]
    return zeilen


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
    inhalt.append(_p(f"{t('bp.aussenmass')}: {ansicht['aussenmass']} mm  ·  {ansicht['anzahl_teile']} "
                     f"{t('bp.einzelteile')}", _klein))
    inhalt += [Spacer(1, 6), _kopf(ansicht["kopf"]), Spacer(1, 8)]

    # Bilder: Entwurf und 3D-Modell nebeneinander (ohne Entwurf das 3D-Modell groß); alles in Holzfarbe
    modell_img = modell_als_bild({**modell, "teile": [{**x, "stil": "holz"} for x in modell["teile"]]})
    if entwurf is not None:
        halb = (BREITE - 6 * mm) / 2
        bilder = Table([[_bild(entwurf, halb), _bild(modell_img, halb)],
                        [_p(t("pdf.entwurf"), _klein), _p(t("pdf.modell"), _klein)]],
                       colWidths=[halb + 3 * mm, halb + 3 * mm], hAlign="LEFT")
        bilder.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        inhalt.append(bilder)
    else:
        inhalt += [_bild(modell_img, BREITE * 0.72), _p(t("pdf.modell"), _klein)]

    # Überblick der Schritte (zum Abhaken)
    zeilen = [[_p(f"{s['nr']}.", ParagraphStyle("nr", parent=_text, fontName="Helvetica-Bold")), _p(s["t"]),
               _p("  ".join(f"{x['n']}× {x['b']}" for x in s["teile"]) or "", _klein), _kaestchen()]
              for s in ansicht["schritte"]]
    inhalt += [_p(t("pdf.ueberblick"), _h2), _tabelle(zeilen, [8 * mm, BREITE - 60 * mm, 42 * mm, 10 * mm], kopf=False)]

    # Die Teile: Übersicht mit Buchstaben und Teileliste
    teile_bild = modellbild({"teile": [{**x, "stil": "holz"} for x in modell["teile"]]}, 2400, 1500, beschriften="alle",
                            hintergrund=(255, 255, 255))
    zeilen = [[_p(t("pdf.buchstabe")), _p(t("pdf.anzahl")), _p(t("pdf.bezeichnung")), _p(t("pdf.holz")), _p(t("pdf.mass"))]]
    zeilen += [[_p(x["b"], ParagraphStyle("b", parent=_text, fontName="Helvetica-Bold")), _p(f"{x['n']}×"), _p(x["name"]),
                _p(x["holz"]), _p(x["mass"])] for x in ansicht["teileliste"]]
    inhalt += [PageBreak(), _p(t("pdf.teile"), _h2), _p(t("pdf.teile_hinweis"), _klein), Spacer(1, 4),
               _bild(teile_bild.resize((1200, 750), Image.LANCZOS), BREITE * 0.85),
               _tabelle(zeilen, [12 * mm, 14 * mm, 50 * mm, 58 * mm, BREITE - 134 * mm])]

    # Einkaufsliste und Werkzeug nebeneinander
    links_b, rechts_b = BREITE * 0.6, BREITE * 0.4
    zeilen = [[_p(t("bp.menge")), _p(t("bp.artikel"))]]
    zeilen += [[_p(f"{l['n']}×"), _p(l["text"])] for l in ansicht["einkauf"]]
    zeilen += [[_p(l["n"]), _p(f"{l['text']} {t('bp.reserve')}")] for l in ansicht["beschlaege"]]
    einkauf = [_p(t("bp.einkauf"), _h2), _tabelle(zeilen, [14 * mm, links_b - 20 * mm]), Spacer(1, 3),
               _p(t("bp.zuschnitt_markt", n=ansicht["schnitte"], preis=eur(0.99), kosten=eur(ansicht["schnittkosten"])),
                  _klein)]
    werkzeug = [_p(t("pdf.werkzeug"), _h2)] + [_p(f"- {w}", _klein) for w in ansicht["werkzeug"]]
    beide = Table([[einkauf, werkzeug]], colWidths=[links_b, rechts_b], hAlign="LEFT")
    beide.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("LEFTPADDING", (1, 0), (1, 0), 10)]))
    inhalt.append(beide)

    # Schritt für Schritt: je Schritt ein Bild (neue Teile orange) und was man dafür braucht
    inhalt += [PageBreak()]
    vorher: set[str] = set()
    for s in ansicht["schritte"]:
        ids = set(s["ids"])
        if ids:
            bild = _schrittbild(modell, ids, vorher)
        else:  # letzter Schritt: alles fertig
            bild = modellbild({**modell, "teile": [{**x, "stil": "holz"} for x in modell["teile"]]}, 3000, 2000,
                              hintergrund=(255, 255, 255)).resize((1500, 1000), Image.LANCZOS)
        links = BREITE * 0.62
        rechts = [_p(t("pdf.brauchst"), _h3)] + _brauchst(s)
        zeile = Table([[_bild(bild, links - 4 * mm), rechts]], colWidths=[links, BREITE - links], hAlign="LEFT")
        zeile.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("BACKGROUND", (1, 0), (1, 0), BEIGE),
                                   ("LEFTPADDING", (1, 0), (1, 0), 7), ("TOPPADDING", (1, 0), (1, 0), 6)]))
        block = [_p(f"{t('pdf.schritt', n=s['nr'])}: {s['t']}", _h3), zeile]
        if s.get("tipp"):
            tipp = Table([[_p(f"{t('pdf.tipp')}: {s['tipp']}", _klein)]], colWidths=[BREITE], hAlign="LEFT")
            tipp.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, 0), 2.5, ORANGE),
                                      ("LEFTPADDING", (0, 0), (0, 0), 7)]))
            block += [Spacer(1, 3), tipp]
        block.append(Spacer(1, 8))
        inhalt.append(KeepTogether(block))
        vorher |= ids

    # Zuschnittplan
    inhalt += [PageBreak(), _p(t("bp.zuschnittplan"), _h2)]
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

    doc.build(inhalt, onFirstPage=seite, onLaterPages=seite)
    return puffer.getvalue()
