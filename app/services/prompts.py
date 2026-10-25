"""Anweisungen an die Bild-KI und an Claude."""
from __future__ import annotations

import json

from ..i18n import t
from ..models.bauteilgraph import GRAPH_SCHEMA


BAUREGELN = (
    "Built by a DIY woodworker from straight solid pine lumber: square battens, planed beams and glued pine boards, "
    "visible screws allowed, simple butt joints, no curves, no metal frame, no upholstery other than loose cushions. "
    "Only this one piece of furniture, nothing else is added: the rest of the area stays empty floor and wall as in the room. "
    "Stands on the floor, realistic proportions, photorealistic, matches the lighting and perspective of the photo."
)


def inpaint_prompt(wunsch: str | None) -> str:
    """Prompt ohne Claude: der Wunsch wörtlich, die Bauregeln stehen fest dabei."""
    w = (wunsch or "").strip() or "a beautiful, simple piece of furniture that fits this corner"
    return f"A handmade piece of furniture in this exact spot of the room: {w}. {BAUREGELN}"


def inpaint_prompt_aus(beschreibung: str) -> str:
    """Prompt aus Claudes englischer Beschreibung plus feste Bauregeln."""
    return f"{beschreibung.strip()} {BAUREGELN}"


def bildprompt_anweisung(wunsch: str | None) -> str:
    """Claude übersetzt den Wunsch in eine präzise englische Beschreibung für die Bild-KI (Inpainting)."""
    w = (wunsch or "").strip() or "ein schönes, schlichtes Möbelstück, das in diese Ecke passt"
    return f"""Du schreibst die Beschreibung für eine Bild-KI (FLUX Fill, Inpainting), die ein selbstgebautes Holzmöbel in ein Wohnungsfoto malt.
Bild 1 ist das Foto. Bild 2 ist die Maske: Nur im weißen Bereich wird neu gemalt.
Wunsch der Person: "{w}"

Schreibe auf Englisch, höchstens 70 Wörter, NUR die Beschreibung, ohne Einleitung:
- genau EIN zusammenhängendes Möbelstück (darf L-förmig oder mehrteilig verbunden sein, z. B. Sofa mit angesetzter Liegefläche), keine weiteren Gegenstände wie Tische, Teppiche oder Deko
- Lage und Ausrichtung mit sichtbaren Bezugspunkten aus dem Foto (z. B. "along the wall below the window, facing the room"), damit die Bild-KI sie versteht
- Form, grobe Größe, Holzart/Farbe, Polster nur als lose Kissen
Bauregeln (gerade Latten und Bretter, keine Rundungen) hängt die App selbst an."""


def _mm(werte: list[float]) -> str:
    return " × ".join(str(int(v)) if float(v).is_integer() else str(v) for v in werte)


def _namen() -> str:
    """Zusatz für die Sprache der Bauteilnamen (leer auf Deutsch, dem Standard)."""
    zusatz = t("prompt.namen")
    return f"\n{zusatz}" if zusatz else ""


def lese_prompt(bereich: list[float]) -> str:
    return f"""Du bist Schreiner und liest aus einem Entwurfsbild die Konstruktion eines Möbels für einen Bauplan-Generator.
Das Bild zeigt das neue Möbel in einer Wohnung. Beschreibe nur dieses Möbel. Zerlege es in Holzteile aus dem Sortiment und fasse gleiche Teile als Gruppe zusammen (anzahl + achse).
Der Platz in der Wohnung ist {_mm(bereich)} mm (Breite × Tiefe × Höhe). Das Möbel muss hineinpassen.
Wähle "funktion": Bett oder Daybed mit Matratze (Normgrößen 900×2000, 1400×2000, 1600×2000) und "anker.liegeflaeche"; Sofa oder Bank mit "sitzhoehe" (Lounge ca. 300, normal 450), "polster" und "anker.sitz_oben"; sonst {{}}.
Wichtiger als exakte Übereinstimmung mit dem Bild: Das Möbel muss baubar und stabil sein.
Leseregeln (aus Blindtests gegen echte Baupläne):
1. Maßstab über Normen: Matratze, Sitzkissen (ca. 60 × 60 cm, Tiefe = Kissentiefe + ca. 5 cm), Sitzhöhe 42–46 cm. Nur ohne solchen Anker: waagrechte Längen in Schrägansicht 10–15 % größer schätzen.
2. Querschnitte im Zweifel eine Nummer kleiner. Stärke am Stirnende ablesen: Brett oder Latte ist 4–5× so breit wie dick, Rahmenholz etwa 2×.
3. Was verkleidet oder belegt (Kopfteil, Seitenverkleidung, sichtbare Sitzlatten), ist dünn: Latte oder Leimholz. Was trägt (Beine, Zargen, Rahmen), ist Rahmenholz.
4. Selbstbau-Möbel nutzen oft ein durchgehendes Profil. Ähnlich aussehende Teile bekommen dasselbe.
5. Verdeckte Teile (unter Polster oder Matratze) nicht erfinden: Standard annehmen, also Lattenrost auf Auflageleisten oder wenige lange Längsbretter.
6. Kästen sind oft je Seite ein Rahmen mit Latten dazwischen statt Pfosten mit Platte.
7. Breite glatte Flächen sind oft Blenden vor einer Unterkonstruktion. Überstehende Kanten sind oft flach aufgelegte Bretter.
8. Wirkt ein Bett schwebend, ist der Rahmen schmaler als die Matratze: Liegefläche-Anker dann unter 0 bzw. über 1.
9. Sofa und Bank: Die Latten oder Bretter, auf denen man sitzt, haben die Rolle "sitzflaeche" (nicht "lattenrost", der ist nur für Betten). "anker.sitz_oben" = Oberkante dieser Sitzlatten OHNE Polster geteilt durch die Gesamthöhe inkl. Lehne; es muss gelten sitz_oben ≈ (sitzhoehe − polster) / masse.hoehe.
10. An der Wand befestigt: Rolle "wandleiste". Verbindende Leisten ohne Last: Rolle "leiste". Schräge Teile gibt es nicht, beschreibe sie achsparallel.
Antworte mit dem Bauteilgraph als JSON. Bedeutung der Felder:
{GRAPH_SCHEMA}{_namen()}"""


def pruef_prompt(graph: dict, bereich: list[float]) -> str:
    """Selbstkontrolle: Claude vergleicht das berechnete Modell mit dem Entwurf und korrigiert den Graph."""
    return f"""Du bist Schreiner und prüfst einen Bauplan-Generator.
Bild 1 ist der Entwurf: ein Möbel in einem Wohnungsfoto (Ausschnitt).
Bild 2 zeigt das Möbel, das der Generator aus dem unten stehenden Bauteilgraph berechnet hat, von vorne links oben gesehen.
Hell: Holz aus dem Graph. Orange: vom Code für die Stabilität ergänzt (Absicht, nicht bemängeln). Grau: Polster oder Matratze.
Der Platz in der Wohnung ist {_mm(bereich)} mm (Breite × Tiefe × Höhe).

Vergleiche Bild 2 mit Bild 1: Art und Form des Möbels, Lehne, Armlehnen, Beine, Richtung der Latten (waagrecht oder senkrecht),
Proportionen (Höhe zu Breite zu Tiefe), Sitz- bzw. Liegehöhe. Fehlen sichtbare Teile, oder gibt es Teile, die im Entwurf nicht vorkommen?
Schweben Teile oder stecken sie ineinander?

Passt es im Wesentlichen: "passt": true, "maengel": [], "graph" unverändert.
Sonst: "passt": false, "maengel" = kurze Liste, je ein Satz {t("prompt.maengel_sprache")}, und "graph" = der vollständige korrigierte
Bauteilgraph. Ändere nur, was nötig ist; Maße, Verbindungen und Statik rechnet danach wieder der Code.

Bauteilgraph:
{json.dumps(graph, ensure_ascii=False)}

Bedeutung der Felder:
{GRAPH_SCHEMA}{_namen()}"""


def anpass_prompt(graph: dict, wunsch: str) -> str:
    return f"""Hier ist der Bauteilgraph eines Möbels:
{json.dumps(graph, ensure_ascii=False)}

Ändere ihn nach diesem Wunsch: "{wunsch}".
Behalte alles andere bei. Das Möbel muss baubar und stabil bleiben; Maße, Verbindungen und Statik rechnet danach Code.
Antworte mit dem vollständigen geänderten Bauteilgraph als JSON. Bedeutung der Felder:
{GRAPH_SCHEMA}{_namen()}"""


KONTEXT_REGELN = ("Keep it built from straight pine battens and boards, no curves. "
                  "Keep everything else in the photo exactly the same: same camera angle, same lighting, same room.")


def bearbeitung_prompt(anpassung: str) -> str:
    """Anweisung für FLUX Kontext ohne Claude: die Änderung wörtlich."""
    return f"Change only the newly built wooden furniture: {anpassung.strip()}. {KONTEXT_REGELN}"


def bearbeitung_anweisung(wunsch: str | None, anpassung: str) -> str:
    """Claude formuliert die Änderung als präzise englische Bearbeitungsanweisung für FLUX Kontext."""
    w = (wunsch or "").strip() or "ein selbstgebautes Holzmöbel"
    return f"""Das Bild zeigt einen Entwurf: ein selbstgebautes Holzmöbel in einem Wohnungsfoto. Ursprünglicher Wunsch: "{w}".
Die Person möchte jetzt nachjustieren: "{anpassung.strip()}"

Schreibe EINE englische Bearbeitungsanweisung für die Bild-KI FLUX Kontext, höchstens 50 Wörter, NUR die Anweisung:
- nenne das Möbel eindeutig mit sichtbaren Merkmalen (z. B. "the light wooden daybed below the window")
- beschreibe nur die gewünschte Änderung, konkret (Farbe genau, Größe relativ: "about 20 cm higher")
- ändere nichts anderes am Möbel als gewünscht
Die App hängt selbst an: {KONTEXT_REGELN}"""
