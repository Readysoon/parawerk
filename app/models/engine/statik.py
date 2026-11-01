"""Statik als Vorbemessung: hält jedes Teil die Normlasten? Nach Eurocode 5 (Holz), Lasten nach den Möbelnormen.

Kein Ersatz für eine geprüfte Statik, aber nachvollziehbar gerechnet statt Faustregel:

Lasten (Nutzer bis 110 kg, wie in den Normen)
- Sitz- und Liegeflächen: 1300 N (EN 12520 / EN 1728), wirkt auf 300 mm Breite und 300 mm Länge (Sitzfläche)
- tragende Hölzer darunter: 80 % davon (Kantenlast), bei langen Bänken je 600 mm eine Person
- Durchbiegung mit dem echten Gewicht (110 kg): Sitz L/150, Liegefläche L/100 (Latten federn), Träger L/200
- Regalböden: 1,5 kg/dm² Dauerlast (EN 16122), Durchbiegung höchstens 0,5 % der Spannweite
- Kippen von Sitzmöbeln: 600 N + 20 N nach vorne/zur Seite, nach hinten 0,2857·(1000 − Sitzhöhe) an der Lehne (EN 1022)

Holz: Nadelholz C24 (f_m,k 24, f_v,k 4,0, f_c,0,k 21 N/mm², E 11 000, E_0,05 7 400), γ_M = 1,3,
k_mod 0,9 (kurze Last: Person) bzw. 0,6 (Dauerlast: Bücher), k_def 0,6. Leimholz wird vorsichtig wie C24 gerechnet.
Schrauben (Bemessungswerte je Schraube, Nadelholz): 6 mm ≈ 1,43 kN, 4 mm ≈ 0,42 kN Abscheren; je Verbindung 2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .grundlagen import SLATS, Bauteil, cen, ext, gesetzt

# Lasten
PERSON = 1300.0  # N, Sitz-Prüflast EN 12520 (Festigkeit)
GEBRAUCH = 110 * 9.81  # N, Nutzer mit 110 kg (Durchbiegung: wie fühlt es sich an)
KANTE = 0.8  # Anteil der Last auf dem vorderen Träger, wenn jemand vorne auf der Kante sitzt (EN 1728 Kantenlast)
PERSON_BREITE = 600.0  # mm Platz je Person nebeneinander
LASTBREITE = 300.0  # mm, über diese Breite verteilt sich eine Person auf Latten
REGAL_Q = 1.5 * 9.81 / 10_000  # 1,5 kg/dm² in N/mm²
KIPP_SENKRECHT, KIPP_WAAGRECHT, KIPP_ABSTAND = 600.0, 20.0, 60.0

# Holz C24 und Sicherheitsbeiwerte
F_M_K, F_V_K, F_C0_K = 24.0, 4.0, 21.0
E_MEAN, E_005 = 11_000.0, 7_400.0
GAMMA_M = 1.3
KMOD_KURZ, KMOD_DAUER = 0.9, 0.6
K_DEF = 0.6
DICHTE = 4.5e-7  # kg/mm³ (450 kg/m³)
SCHRAUBE_RD = {6: 1430.0, 4: 420.0}  # N je Schraube, Abscheren
SCHRAUBEN_JE_VERBINDUNG = 2

TRAEGER = {"auflage", "rahmen", "zarge", "mittelsteg", "querriegel", "wandleiste"}
STUETZEN = {"bein", "pfosten", "stuetze"}
PERSONEN_FLAECHEN = {"sitzflaeche", "liegeflaeche", "lattenrost"}


@dataclass
class Nachweis:
    """Ergebnis für ein Teil: höchste Ausnutzung (1,0 = 100 %) und welcher Nachweis sie bestimmt."""
    teil: Bauteil
    ausnutzung: float
    art: str  # biegung, schub, durchbiegung, knicken, schrauben
    werte: dict = field(default_factory=dict)


@dataclass
class Statik:
    nachweise: list[Nachweis]
    kippen: dict | None  # {"ausnutzung", "richtung"} oder None, wenn nicht zu prüfen

    @property
    def schlechtester(self) -> Nachweis | None:
        return max(self.nachweise, key=lambda n: n.ausnutzung, default=None)


def _fd(fk: float, kmod: float) -> float:
    return kmod * fk / GAMMA_M


def _querschnitt(m: Bauteil) -> tuple[float, float]:
    """Breite b (waagrecht quer) und Höhe h (senkrecht) eines liegenden Teils."""
    quer = next(a for a in (0, 1) if a != m.long)
    return ext(m, quer), ext(m, 2)


def _personen_nutzung(g: dict, ms: list[Bauteil]) -> bool:
    f = g.get("funktion") or {}
    return (gesetzt(f.get("sitzhoehe")) or gesetzt(f.get("matratze"))
            or g.get("kategorie") in ("bank", "sofa", "daybed", "bett", "tisch")
            or any(m.rolle in PERSONEN_FLAECHEN for m in ms))


def _teilung(m: Bauteil, ms: list[Bauteil]) -> float:
    """Abstand zur nächsten Latte derselben Reihe (Mitte zu Mitte), sonst die eigene Breite."""
    quer = next(a for a in (0, 1) if a != m.long)
    nachbarn = [abs(cen(o, quer) - cen(m, quer)) for o in ms if o is not m and o.part == m.part]
    return min(nachbarn) if nachbarn else ext(m, quer)


def _balken(m: Bauteil, L: float, auskragung: bool, P: float = 0.0, q: float = 0.0, kmod: float = KMOD_KURZ,
            grenze: float = 300.0, kriechen: bool = False, gebrauch: float = 1.0) -> Nachweis:
    """Einfeldträger (bzw. Kragarm) mit Last P auf 300 mm Länge in der Mitte (bzw. am Ende) und Streckenlast q.

    Festigkeit mit den Prüflasten; Durchbiegung mit ``gebrauch`` × Last (echtes Gewicht statt Prüflast).
    """
    b, h = _querschnitt(m)
    W, I = b * h * h / 6, b * h ** 3 / 12
    a = min(LASTBREITE, L)  # Länge, auf der die Person aufliegt
    if auskragung:  # spannweite() meldet bei Kragarmen die doppelte Länge
        c = L / 2
        M, V = P * c + q * c * c / 2, P + q * c
        w = P * c ** 3 / (3 * E_MEAN * I) + q * c ** 4 / (8 * E_MEAN * I)
        w_grenze = 2 * c / grenze
    else:
        M, V = P * (2 * L - a) / 8 + q * L * L / 8, P / 2 + q * L / 2
        w = P * L ** 3 / (48 * E_MEAN * I) + 5 * q * L ** 4 / (384 * E_MEAN * I)
        w_grenze = L / grenze
    w *= gebrauch
    if kriechen:
        w *= 1 + K_DEF
    aus = {"biegung": (M / W) / _fd(F_M_K, kmod), "schub": (1.5 * V / (b * h)) / _fd(F_V_K, kmod),
           "durchbiegung": w / w_grenze if w_grenze > 0 else 0.0}
    art = max(aus, key=aus.get)
    return Nachweis(m, aus[art], art, {"L": round(L), "M": round(M), "V": round(V), "w": round(w, 1),
                                       "w_grenze": round(w_grenze, 1), **{k: round(v, 3) for k, v in aus.items()}})


def _knicken(m: Bauteil, N: float) -> Nachweis:
    """Druckstab (Bein, Pfosten), beidseitig gelenkig, Knicklänge = Länge (Eurocode 5, 6.3.2)."""
    a, b = ext(m, 0), ext(m, 1)
    L = ext(m, 2)
    i = min(a, b) / math.sqrt(12)
    lam_rel = (L / i) / math.pi * math.sqrt(F_C0_K / E_005)
    k = 0.5 * (1 + 0.2 * (lam_rel - 0.3) + lam_rel ** 2)
    kc = min(1.0, 1 / (k + math.sqrt(max(k * k - lam_rel ** 2, 0.0))))
    sigma = N / (a * b)
    aus = sigma / (kc * _fd(F_C0_K, KMOD_KURZ))
    return Nachweis(m, aus, "knicken", {"N": round(N), "kc": round(kc, 3), "L": round(L)})


def _eigengewicht(ms: list[Bauteil]) -> tuple[float, list[float]]:
    """Gewicht in N und Schwerpunkt (x, y) aller Teile."""
    vol = [ext(m, 0) * ext(m, 1) * ext(m, 2) for m in ms]
    V = sum(vol) or 1.0
    return V * DICHTE * 9.81, [sum(v * cen(m, a) for v, m in zip(vol, ms)) / V for a in (0, 1)]


def _kippen(ms: list[Bauteil], sitz: list[Bauteil]) -> dict | None:
    """EN 1022: Sitzmöbel darf beim Belasten der Kante nicht kippen. Ausnutzung = Kippmoment / Standmoment."""
    boden = [m for m in ms if m.min[2] <= 0.5]
    if not boden or not sitz:
        return None
    G, cg = _eigengewicht(ms)
    hoehe = max(m.max[2] for m in sitz)
    ergebnisse = []
    for achse, richtung in ((1, "vorne"), (0, "seite")):
        kante = min(m.min[achse] for m in boden)  # Kippkante: vorderster bzw. linkester Bodenkontakt
        last = min(m.min[achse] for m in sitz) + KIPP_ABSTAND  # 60 mm innerhalb der Sitzkante
        kipp = KIPP_WAAGRECHT * hoehe + max(0.0, kante - last) * KIPP_SENKRECHT
        stand = G * (cg[achse] - kante) + max(0.0, last - kante) * KIPP_SENKRECHT
        ergebnisse.append((kipp / stand if stand > 0 else 9.0, richtung))
    lehne = [m for m in ms if m.rolle == "lehne"]
    if lehne:  # nach hinten: Kraft oben an der Lehne
        kante = max(m.max[1] for m in boden)
        F = 0.2857 * max(0.0, 1000 - hoehe)
        z = max(m.max[2] for m in lehne)
        sitz_mitte = sum(cen(m, 1) for m in sitz) / len(sitz)
        stand = G * (kante - cg[1]) + KIPP_SENKRECHT * (kante - sitz_mitte)
        ergebnisse.append((F * z / stand if stand > 0 else 9.0, "hinten"))
    aus, richtung = max(ergebnisse)
    return {"ausnutzung": aus, "richtung": richtung}


def _getragen(m: Bauteil, J: list[dict]) -> list[Bauteil]:
    """Flächen, die auf dem Träger liegen: direkt oben drauf oder auf einer seitlich angeschraubten Auflageleiste."""
    def nachbarn(x: Bauteil) -> list[tuple[Bauteil, int]]:
        return [((j["b"] if j["a"] is x else j["a"]), j["ax"]) for j in J if j["a"] is x or j["b"] is x]

    oben = [o for o, ax in nachbarn(m) if ax == 2 and o.rolle in SLATS and o.min[2] >= m.max[2] - 1.5]
    for a, ax in nachbarn(m):
        if ax != 2 and a.rolle == "auflage":
            oben += [o for o, ax2 in nachbarn(a) if ax2 == 2 and o.rolle in SLATS and o.min[2] >= a.max[2] - 1.5]
    return oben


def liegend(m: Bauteil, L: float, krag: bool, ms: list[Bauteil], J: list[dict], g: dict,
            personen: bool | None = None) -> Nachweis | None:
    """Nachweis für ein liegendes Teil mit freier Spannweite L; None, wenn es keine Nutzlast trägt."""
    personen = _personen_nutzung(g, ms) if personen is None else personen
    if m.rolle in SLATS:
        if m.rolle == "regalboden" and not personen:
            return _balken(m, L, krag, q=REGAL_Q * _querschnitt(m)[0], kmod=KMOD_DAUER, grenze=200, kriechen=True)
        anteil = min(1.0, max(_teilung(m, ms), _querschnitt(m)[0]) / LASTBREITE)
        grenze = 150.0 if m.rolle in ("sitzflaeche", "regalboden") else 100.0
        return _balken(m, L, krag, P=PERSON * anteil, grenze=grenze, gebrauch=GEBRAUCH / PERSON)
    if m.rolle not in TRAEGER:
        return None
    oben = _getragen(m, J)
    if not oben:
        return None
    if personen:
        n = _balken(m, L, krag, P=KANTE * PERSON, grenze=200, gebrauch=GEBRAUCH / PERSON)
        n2 = _balken(m, L, krag, q=0.5 * PERSON / PERSON_BREITE, grenze=200,  # mehrere Personen nebeneinander
                     gebrauch=GEBRAUCH / PERSON)
        n = n if n.ausnutzung >= n2.ausnutzung else n2
    else:
        quer = next(a for a in (0, 1) if a != m.long)
        n = _balken(m, L, krag, q=REGAL_Q * max(ext(o, quer) for o in oben) / 2, kmod=KMOD_DAUER, grenze=200,
                    kriechen=True)
    # Verschraubung an den Enden: Auflagerkraft gegen 2 Schrauben je Verbindung
    d = 6 if m.typ == "kantholz" else 4
    aus = n.werte["V"] / (SCHRAUBEN_JE_VERBINDUNG * SCHRAUBE_RD[d])
    return Nachweis(m, aus, "schrauben", {**n.werte, "d": d}) if aus > n.ausnutzung else n


def grenz_spannweite(m: Bauteil, ms: list[Bauteil], J: list[dict], g: dict, krag: bool = False) -> float:
    """Größte freie Spannweite, die das Teil mit seinen Lasten noch hält (Biegung, Schub, Durchbiegung).

    ``krag``: Kragarm. Wie bei ``spannweite`` zählt seine Länge doppelt.
    """
    personen = _personen_nutzung(g, ms)
    if liegend(m, 100.0, False, ms, J, g, personen) is None:
        return math.inf  # trägt nichts
    lo, hi = 50.0, 8000.0
    for _ in range(30):
        mitte = (lo + hi) / 2
        n = liegend(m, mitte, krag, ms, J, g, personen)
        if n is not None and n.art != "schrauben" and n.ausnutzung > 1:
            hi = mitte
        else:
            lo = mitte
    return lo


def statik(ms: list[Bauteil], J: list[dict], g: dict) -> Statik:
    from .reparatur import spannweite  # hier, weil reparatur selbst auf die Prüfung zugreift

    personen = _personen_nutzung(g, ms)
    nachweise: list[Nachweis] = []
    flaechen = [m for m in ms if m.rolle in SLATS and m.long != 2]

    # 1. Liegende Teile: Flächen (Latten, Bretter, Regalböden) und Träger darunter
    for m in ms:
        if m.long == 2 or (m.rolle not in SLATS and m.rolle not in TRAEGER):
            continue
        si = spannweite(m, J)
        if not si["supported"] or not si["worst"]["len"]:
            continue
        n = liegend(m, si["worst"]["len"], bool(si["worst"].get("cant")), ms, J, g, personen)
        if n is not None:
            nachweise.append(n)

    # 2. Beine und Pfosten (Druck mit Knicken)
    stuetzen = [m for m in ms if m.rolle in STUETZEN and m.long == 2 and m.min[2] <= 0.5]
    if stuetzen:
        if personen:
            breite = max((ext(m, 0) for m in flaechen), default=PERSON_BREITE)
            last = PERSON * max(1, round(breite / PERSON_BREITE))
        else:
            last = sum(REGAL_Q * ext(m, 0) * ext(m, 1) for m in flaechen)
        last += _eigengewicht(ms)[0]
        N = last / max(1.0, len(stuetzen) / 2)  # die Hälfte der Beine trägt alles (Last auf einer Seite)
        nachweise += [_knicken(m, N) for m in stuetzen]

    sitz = [m for m in ms if m.rolle == "sitzflaeche"] or ([m for m in flaechen if m.rolle in PERSONEN_FLAECHEN]
                                                            if gesetzt((g.get("funktion") or {}).get("sitzhoehe")) else [])
    kippen = None if any(m.rolle == "wandleiste" for m in ms) else _kippen(ms, sitz)
    return Statik(nachweise, kippen)
