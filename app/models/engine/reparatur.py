"""Schritt 4: Prüfen und reparieren.

Reihenfolge je Durchlauf: Handelslänge, Liegefläche frei, Lattenabstand, fehlende Auflager, Spannweiten,
Aussteifung. Nach jeder Reparatur werden die Teile neu gesetzt und es geht von vorn los (höchstens 12-mal).
"""
from __future__ import annotations

import math

from ...i18n import holz, t, und, zitat
from ..sortiment import Sortiment, handelslaengen, naechstes_kantholz
from .grundlagen import (
    ATTACH,
    AXN,
    LOADED,
    SLATS,
    Bauteil,
    cen,
    depth,
    einmalig,
    eintraege,
    ext,
    gesetzt,
    mm,
    others,
    ov,
    prio,
    quader,
    rollenname,
    zahl,
)
from .setzen import kontakte, setzen

GURT_FREI = 60  # mm, so weit darf ein Gurtende über die Zarge hinausstehen


def _auf_bein_legen(ms: list[Bauteil], m: Bauteil, J: list[dict]) -> bool:
    """Liegt ein liegendes Teil mit einem Ende frei neben dem Kopf eines Beins, wird es über das Bein verbreitert.

    Stößt es dabei an ein anderes stehendes Teil (den Pfosten), endet es vor diesem und wird dort angeschraubt.
    Nur für Bretter und Leisten, die nicht zu einer Fläche (Latten) gehören.
    """
    if m.long == 2 or m.rolle in SLATS or m.typ == "gurt" or m.min[2] < 30 or m.origin != "entwurf":
        return False
    si = spannweite(m, J)
    if not si.get("supported") or not si["worst"].get("cant") or si["worst"]["len"] < 160:
        return False
    L = m.long
    q = next(a for a in (0, 1) if a != L)
    frei_min = si["worst"]["at"] < cen(m, L)  # freies Ende am Anfang oder am Ende der Längsachse
    ende = m.min[L] if frei_min else m.max[L]
    beine = [v for v in ms if v.long == 2 and abs(v.max[2] - m.min[2]) <= 1.5 and v.rolle in ("bein", "pfosten", "stuetze")
             and v.min[L] <= ende + 1 and v.max[L] >= ende - 1 and -1.5 <= -ov(m, v, q) <= 1.5]
    if not beine:
        return False
    v = beine[0]
    alt = (list(m.min), list(m.max))
    m.min[q], m.max[q] = min(m.min[q], v.min[q]), max(m.max[q], v.max[q])
    for o in ms:  # an stehenden Teilen auf dem Weg zum anderen Ende enden
        if o is m or o is v or depth(m, o) <= 0.5:
            continue
        if o.long == 2:
            if frei_min:
                m.max[L] = min(m.max[L], o.min[L])
            else:
                m.min[L] = max(m.min[L], o.max[L])
    ok = (m.max[L] - m.min[L] > 0.5 * (alt[1][L] - alt[0][L])
          and not any(o is not m and depth(m, o) > 0.5 for o in ms))
    if not ok:
        m.min, m.max = alt
        return False
    if "w" in m.prof:
        m.prof = {**m.prof, "w": round(m.max[q] - m.min[q])}
    return True


def _gurte_verlaengern(ms: list[Bauteil], m: Bauteil) -> bool:
    """Gurtenden, die knapp vor einer Zarge auf gleicher Höhe enden, bis über diese Zarge verlängern (die ganze Reihe).

    So werden die Gurte dort festgetackert, wo auch im Echten getackert wird: oben auf dem Rahmen.
    """
    L, quer = m.long, next(a for a in (0, 1) if a != m.long)
    reihe = [o for o in ms if o.part == m.part]
    neu: dict = {}
    for seite in ("min", "max"):
        ende = m.min[L] if seite == "min" else m.max[L]
        def nah(o: Bauteil) -> bool:
            if o.part == m.part or prio(o) < 4 or abs(o.max[2] - m.min[2]) > 2 or ov(m, o, quer) < 30:
                return False
            if seite == "max":
                return ende - 1.5 <= o.min[L] <= ende + 2 * GURT_FREI and o.max[L] > ende + 1
            return ende - 2 * GURT_FREI <= o.max[L] <= ende + 1.5 and o.min[L] < ende - 1
        traeger = [o for o in ms if nah(o)]
        if traeger:
            neu[seite] = (max if seite == "max" else min)(o.max[L] if seite == "max" else o.min[L] for o in traeger)
    if not neu:
        return False
    geaendert = False
    for g in reihe:  # einzeln: Gurte neben einem Pfosten bleiben kürzer
        alt = g.min[L], g.max[L]
        g.min[L] = min(g.min[L], neu.get("min", g.min[L]))
        g.max[L] = max(g.max[L], neu.get("max", g.max[L]))
        if (g.min[L], g.max[L]) == alt:
            continue
        if any(depth(g, o) > 0.5 for o in ms if o.part != m.part):
            g.min[L], g.max[L] = alt
        else:
            geaendert = True
    return geaendert

def gurtrahmen(S: Sortiment, ms: list[Bauteil]) -> list[str]:
    """Gurtsitz auf einen geschlossenen Rahmen setzen: Zargen unter beiden Gurtenden (dort wird getackert) und an
    beiden Seiten. So ziehen die Gurte nicht nur an zwei losen Zargen, und vorne gibt es eine feste Sitzkante.
    Gibt die Namen der Gurtreihen zurück, an denen etwas ergänzt wurde."""
    from . import gurte as gu
    ergaenzt = []
    for part in einmalig(m.part for m in ms if m.typ == "gurt"):
        reihe = [m for m in ms if m.part == part]
        L = reihe[0].long
        Q = next(a for a in (0, 1) if a != L)
        lo = [min(m.min[a] for m in reihe) for a in (0, 1, 2)]
        hi = [max(m.max[a] for m in reihe) for a in (0, 1, 2)]
        z0 = lo[2]

        def traeger(o: Bauteil) -> bool:
            return o.typ != "gurt" and o.long != 2 and prio(o) >= 4 and z0 - 25 <= o.max[2] <= z0 + 1.5

        def ueberlappt(o: Bauteil, a: int, von: float, bis: float) -> float:
            return min(o.max[a], bis) - max(o.min[a], von)

        holz = [o for o in ms if traeger(o)]
        voll = 0.5 * (hi[Q] - lo[Q])
        enden = {0: [o for o in holz if o.long == Q and ueberlappt(o, L, lo[L], lo[L] + 150) >= 15
                     and ueberlappt(o, Q, lo[Q], hi[Q]) >= voll],
                 1: [o for o in holz if o.long == Q and ueberlappt(o, L, hi[L] - 150, hi[L]) >= 15
                     and ueberlappt(o, Q, lo[Q], hi[Q]) >= voll]}
        # Gurte enden auf der äußeren Kante der Endzarge (dort getackert), nicht frei dahinter
        if enden[0]:
            kante = min(o.min[L] for o in enden[0])
            for m in reihe:
                m.min[L] = max(m.min[L], kante)
            lo[L] = max(lo[L], kante)
        if enden[1]:
            kante = max(o.max[L] for o in enden[1])
            for m in reihe:
                m.max[L] = min(m.max[L], kante)
            hi[L] = min(hi[L], kante)
        def seite(o: Bauteil, rand: float) -> bool:  # Zarge längs der Gurte am Rand (innen oder außen daneben)
            return o.long == L and abs(cen(o, Q) - rand) <= 120 and ueberlappt(o, L, lo[L], hi[L]) >= 0.5 * (hi[L] - lo[L])
        seiten = {0: [o for o in holz if seite(o, lo[Q])], 1: [o for o in holz if seite(o, hi[Q])]}
        vorbild = next((o for o in [*seiten[0], *seiten[1], *enden[0], *enden[1]] if o.typ == "kantholz"), None)
        if vorbild is not None:
            quer = next(a for a in (0, 1) if a != vorbild.long)
            dick, hoch, prof = ext(vorbild, quer), ext(vorbild, 2), vorbild.prof
        else:
            k = naechstes_kantholz(S, 44, 74)
            dick, hoch, prof = k["a"], k["b"], {"label": k["label"], "a": k["a"], "b": k["b"]}
        gefunden = [*enden[0], *enden[1], *seiten[0], *seiten[1]]
        zt = max((o.max[2] for o in gefunden), default=z0)
        if zt < z0 - 0.5:  # Gurte direkt auf den Rahmen legen
            d = z0 - zt
            for m in reihe:
                m.min[2] -= d
                m.max[2] -= d
            if any(depth(m, o) > 0.5 for m in reihe for o in ms if o.part != part):
                for m in reihe:
                    m.min[2] += d
                    m.max[2] += d
                zt = z0
        # Gurte zwischen vorhandenen Seitenzargen neu verteilen (nicht längs auf einer Zarge liegen lassen)
        innen_lo = max((o.max[Q] for o in seiten[0]), default=None)
        innen_hi = min((o.min[Q] for o in seiten[1]), default=None)
        if innen_lo is not None or innen_hi is not None:
            a = lo[Q] if innen_lo is None else innen_lo + 10
            b = hi[Q] if innen_hi is None else innen_hi - 10
            if b - a >= gu.GURT_BREITE:
                n = gu.anzahl(b - a)
                vorlage = reihe[0]
                for m in reihe:
                    ms.remove(m)
                reihe = []
                for i in range(n):
                    m = vorlage.kopie(id=f"{part}-{i + 1}")
                    m.min[Q] = a + (0 if n == 1 else i * (b - a - gu.GURT_BREITE) / (n - 1))
                    m.max[Q] = m.min[Q] + gu.GURT_BREITE
                    reihe.append(m)
                ms.extend(reihe)
                lo[Q], hi[Q] = a, b
        # wie weit der Rahmen quer reicht: Beine und Pfosten, die bis an den Rahmen hochgehen
        stehend = [o for o in ms if o.long == 2 and o.typ == "kantholz" and o.max[2] >= zt - hoch / 2 and o.min[2] < zt]
        neu = []
        for ende in (0, 1):
            if enden[ende]:
                continue
            q = Bauteil(id=f"{t('teil.gurtzarge')} {part} {'AB'[ende]}", part=f"Gurtzarge {part} {'AB'[ende]}",
                        name=t("teil.gurtzarge"), typ="kantholz", rolle="zarge", prof=prof, long=Q, dax=-1,
                        origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
            q.min[L] = lo[L] if ende == 0 else hi[L] - dick
            q.max[L] = q.min[L] + dick
            nah = [o for o in stehend if ueberlappt(o, L, q.min[L] - 60, q.max[L] + 60) > 0]
            q.min[Q] = min([o.min[Q] for o in nah] + [o.min[Q] for o in seiten[0]] + [lo[Q] - gu.EINZUG])
            q.max[Q] = max([o.max[Q] for o in nah] + [o.max[Q] for o in seiten[1]] + [hi[Q] + gu.EINZUG])
            q.min[2], q.max[2] = zt - hoch, zt
            neu.append(q)
        for seite in (0, 1):
            if seiten[seite]:
                continue
            q = Bauteil(id=f"{t('teil.gurtzarge')} {part} {'LR'[seite]}", part=f"Gurtzarge {part} {'LR'[seite]}",
                        name=t("teil.gurtzarge"), typ="kantholz", rolle="zarge", prof=prof, long=L, dax=-1,
                        origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
            q.min[Q] = lo[Q] - gu.EINZUG if seite == 0 else hi[Q] + gu.EINZUG - dick
            q.max[Q] = q.min[Q] + dick
            nah = [o for o in stehend if ueberlappt(o, Q, q.min[Q] - 60, q.max[Q] + 60) > 0]
            q.min[L] = min([o.min[L] for o in nah] + [lo[L]])
            q.max[L] = max([o.max[L] for o in nah] + [hi[L]])
            q.min[2], q.max[2] = zt - hoch, zt
            neu.append(q)
        for q in neu:
            ms.append(q)
        for q in neu:
            kuerzen(ms, q)
        if neu:
            ergaenzt.append(reihe[0].name)
    return ergaenzt


def _beruehrt(J: list[dict], a: Bauteil, b: Bauteil) -> bool:
    return any((j["a"] is a and j["b"] is b) or (j["a"] is b and j["b"] is a) for j in J)


def spannweite(m: Bauteil, J: list[dict]) -> dict:
    """Größte freie Spannweite eines liegenden Teils (Auskragungen zählen doppelt)."""
    L = m.long
    iv = []
    if m.min[2] <= 0.5 or m.rolle == "wandleiste":
        iv.append([m.min[L], m.max[L]])
    for j in J:
        if j["a"] is not m and j["b"] is not m:
            continue
        o = j["b"] if j["a"] is m else j["a"]
        if j["ax"] == 2:
            if o.max[2] <= m.min[2] + 1.5:
                iv.append([max(m.min[L], o.min[L]), min(m.max[L], o.max[L])])
        elif j["ax"] == L:
            iv.append([m.min[L], m.min[L] + 20] if o.max[L] <= m.min[L] + 1.5 else [m.max[L] - 20, m.max[L]])
        elif m.rolle not in SLATS and m.rolle != "gurt":
            iv.append([max(m.min[L], o.min[L]), min(m.max[L], o.max[L])])
    if not iv:
        return {"supported": False}
    iv.sort(key=lambda p: p[0])
    merged = [list(iv[0])]
    for s in iv[1:]:
        last = merged[-1]
        if s[0] <= last[1]:
            last[1] = max(last[1], s[1])
        else:
            merged.append(list(s))
    worst: dict = {"len": 0}
    for k in range(1, len(merged)):
        laenge = merged[k][0] - merged[k - 1][1]
        if laenge > worst["len"]:
            worst = {"len": laenge, "at": (merged[k][0] + merged[k - 1][1]) / 2}
    c0, c1 = merged[0][0] - m.min[L], m.max[L] - merged[-1][1]
    if 2 * c0 > worst["len"]:
        worst = {"len": 2 * c0, "at": m.min[L] + c0 / 2, "cant": True}
    if 2 * c1 > worst["len"]:
        worst = {"len": 2 * c1, "at": m.max[L] - c1 / 2, "cant": True}
    return {"supported": True, "worst": worst}


def max_spannweite(m: Bauteil, ms: list[Bauteil], J: list[dict], g: dict, krag: bool = False) -> float:
    """Größte freie Spannweite nach der Statik (Normlasten, Eurocode 5); unendlich, wenn das Teil nichts trägt."""
    from .statik import grenz_spannweite
    return grenz_spannweite(m, ms, J, g, krag)


def kuerzen(ms: list[Bauteil], s: Bauteil) -> None:
    """Eingefügtes Teil an Hölzern enden lassen, die es kreuzt (statt hindurchzugehen): Enden an deren Innenseite."""
    L = s.long
    for o in ms:
        if o is s or o.part == s.part or o.rolle in SLATS or depth(s, o) <= 0.5:
            continue
        if cen(o, L) < cen(s, L):
            s.min[L] = max(s.min[L], o.max[L])
        else:
            s.max[L] = min(s.max[L], o.min[L])


def volumen(m: Bauteil) -> float:
    return ext(m, 0) * ext(m, 1) * ext(m, 2)


def staerker_machen(S: Sortiment, ms: list[Bauteil], m: Bauteil, laenge: float, J: list[dict], g: dict,
                    krag: bool = False, nur_volumen: bool = False) -> str | float | None:
    """Stärkeres Holz für die ganze Teilegruppe, wenn es die Spannweite dann hält.

    Bretter werden nach oben dicker (Unterkante bleibt auf den Trägern), Kanthölzer nach unten (Oberkante bleibt).

    Bretter (liegend): nächste Leimholz-Stärke. Kanthölzer: nächst stärkerer Querschnitt, hochkant.
    Gibt das neue Holz zurück (für den Bericht) oder None, wenn es nichts Passendes gibt.
    ``nur_volumen``: nichts ändern, nur sagen, wie viel Holz (mm³) dafür dazukäme.
    """
    if m.origin != "entwurf":
        return None  # eingefügte Stege bekommen lieber eine Stütze als immer dickeres Holz
    quer = next(a for a in (0, 1) if a != m.long)
    alt_label = m.prof.get("label")
    if m.typ == "brett" and abs(ext(m, 2) - m.prof.get("t", 0)) < 0.5:
        kandidaten = [{"t": p["t"]} for p in sorted(S["leimholz"], key=lambda p: p["t"]) if p["t"] > m.prof["t"]]
    elif m.typ == "kantholz":
        jetzt = ext(m, quer) * ext(m, 2) ** 2
        kandidaten = sorted((p for p in S["kantholz"] if min(p["a"], p["b"]) * max(p["a"], p["b"]) ** 2 > jetzt * 1.05),
                            key=lambda p: p["a"] * p["b"])
    else:
        return None
    gruppe = [o for o in ms if o.part == m.part]

    def anwenden(ziel: Bauteil, k: dict) -> None:
        if "t" in k:  # Brett wird nach oben dicker: liegt weiter auf seinen Trägern
            ziel.max[2] = ziel.min[2] + k["t"]
            ziel.prof = {**ziel.prof, "t": k["t"]}
        else:
            b, h = min(k["a"], k["b"]), max(k["a"], k["b"])
            mitte = cen(ziel, quer)
            ziel.min[quer], ziel.max[quer] = mitte - b / 2, mitte + b / 2
            ziel.min[2] = ziel.max[2] - h
            ziel.prof = {"label": k["label"], "a": k["a"], "b": k["b"]}

    for k in kandidaten:
        probe = m.kopie()
        anwenden(probe, k)
        if max_spannweite(probe, [probe if o is m else o for o in ms], J, g, krag) >= laenge:
            if nur_volumen:
                return len(gruppe) * (volumen(probe) - volumen(m))
            for o in gruppe:
                anwenden(o, k)
                if o.origin == "reparatur":
                    kuerzen(ms, o)
            if "label" in k and k["label"] == alt_label:
                return t("rep.hochkant", holz=holz(k["label"]))
            return holz(k["label"]) if "label" in k else t("plan.brett", t=zahl(k["t"]), w=zahl(m.prof.get("w", 0)))
    return None


def _steg_volumen(S: Sortiment, ms: list[Bauteil], groups: dict, m: Bauteil, laenge: float, lm: float) -> float | None:
    """Holz (mm³) für die andere Lösung: Mittelsteg(e) unter einer Reihe bzw. eine Stütze bis zum Boden."""
    if m.rolle in SLATS and m.part in groups:
        if any(o.part == f"Mittelsteg {m.part}" for o in ms):
            return None
        prof = naechstes_kantholz(S, 44, 74)
        dax = groups[m.part]["dax"]
        ps = [o for o in ms if o.part == m.part]
        k = max(1, min(8, math.ceil(laenge / lm) - 1)) if math.isfinite(lm) and lm > 0 else 1
        return k * (max(o.max[dax] for o in ps) - min(o.min[dax] for o in ps)) * prof["a"] * prof["b"]
    if m.min[2] > 30 and not any(o.part == f"Stütze {m.id}" for o in ms):
        prof = naechstes_kantholz(S, 44, 44)
        return m.min[2] * prof["a"] * prof["b"]
    return None


def senkrecht_einsetzen(ms: list[Bauteil], tpl: Bauteil, at: float, along: int, label: str, name: str | None = None) -> int:
    """Pfosten oder Stütze vom Boden nach oben; wo tragende Teile im Weg sind, wird er unterbrochen."""
    L = along
    other = next(a for a in others(2) if a != L)
    base = quader([0, 0, 0], [0, 0, 0])
    base.min[L] = at - ext(tpl, L) / 2
    base.max[L] = at + ext(tpl, L) / 2
    base.min[other], base.max[other] = tpl.min[other], tpl.max[other]
    base.min[2], base.max[2] = tpl.min[2], tpl.max[2]
    blocks = sorted(
        ([o.min[2], o.max[2]] for o in ms
         if o.rolle not in ATTACH and ov(base, o, 0) > 1 and ov(base, o, 1) > 1 and ov(base, o, 2) > 1),
        key=lambda p: p[0],
    )
    z = base.min[2]
    segs = []
    for b0, b1 in blocks + [[base.max[2], base.max[2]]]:
        if b0 - z >= 60:
            segs.append([z, min(b0, base.max[2])])
        z = max(z, b1)
    for k, (z0, z1) in enumerate(segs, start=1):
        m = tpl.kopie(id=f"{label}-{k}" if len(segs) > 1 else label, part=label, name=name or label, origin="reparatur",
                      long=2, dax=-1)
        m.min, m.max = list(base.min), list(base.max)
        m.min[2], m.max[2] = z0, z1
        ms.append(m)
    return len(segs)


def aussteifung(ms: list[Bauteil], J: list[dict]) -> list[dict]:
    """Je Richtung (x = von vorne gesehen, y = von der Seite) prüfen, ob das Gestell gegen Verschieben gesichert ist."""
    if any(m.rolle == "wandleiste" for m in ms):
        return [{"ax": 0, "ok": True, "why": t("why.wand")}, {"ax": 1, "ok": True, "why": t("why.wand")}]
    bb = [[min(m.min[a] for m in ms), max(m.max[a] for m in ms)] for a in (0, 1)]

    def am_rand(v: Bauteil, a: int) -> bool:
        spanne = bb[a][1] - bb[a][0]
        return cen(v, a) - bb[a][0] < 0.25 * spanne or bb[a][1] - cen(v, a) < 0.25 * spanne

    verts = [m for m in ms if m.long == 2 and m.min[2] <= 0.5 and ext(m, 2) > 120 and am_rand(m, 0) and am_rand(m, 1)]
    res = []
    for ax in (0, 1):
        if len(verts) < 2:
            res.append({"ax": ax, "ok": True, "why": t("why.flach")})
            continue
        o = 1 - ax
        # Platte oder Verkleidung in dieser Ebene, die mindestens zwei Beine verbindet
        sheet = next((m for m in ms if m.typ == "brett" and ext(m, ax) >= 300 and ext(m, 2) >= 200 and ext(m, o) <= 30
                      and sum(1 for v in verts if _beruehrt(J, m, v)) >= 2), None)
        if sheet is not None:
            res.append({"ax": ax, "ok": True, "why": t("why.platte", name=sheet.name)})
            continue
        clad = [m for m in ms if m.rolle in ("verkleidung", "lehne") and m.long == ax
                and sum(1 for v in verts if _beruehrt(J, m, v)) >= 2]
        if len(clad) >= 3:
            res.append({"ax": ax, "ok": True, "why": t("why.verkleidung", n=len(clad), rolle=rollenname(clad[0].rolle))})
            continue
        vclad = [m for m in ms if m.rolle in ("verkleidung", "lehne") and m.long == 2 and ext(m, o) <= 30
                 and sum(1 for h in ms if h is not m and h.long != 2 and prio(h) >= 3 and _beruehrt(J, h, m)) >= 2]
        if len(vclad) >= 3:
            res.append({"ax": ax, "ok": True, "why": t("why.senkrecht", n=len(vclad))})
            continue
        # je Bein: Riegel in Richtung ax, ihre Höhen und die freie Beinlänge
        bad = []
        for v in verts:
            rails = [m for m in ms if m is not v and m.long != 2 and prio(m) >= 3 and _beruehrt(J, m, v)
                     and (m.long == ax or ext(m, 2) >= 70)]
            if not rails:
                bad.append({"v": v, "why": t("why.kein_riegel")})
                continue
            zs = sorted(([r.min[2], r.max[2]] for r in rails), key=lambda p: p[0])
            spread = zs[-1][0] - zs[0][1]
            free = zs[0][0]
            tiefe = max(ext(r, 2) for r in rails)
            if spread >= 0.25 * ext(v, 2):
                continue  # zwei Riegelebenen
            if free <= 450 and tiefe >= 70:
                continue  # kurze Beine an breiter Zarge
            bad.append({"v": v, "why": t("why.beinlaenge", laenge=mm(free))})
        res.append({"ax": ax, "ok": False, "bad": bad} if bad
                   else {"ax": ax, "ok": True, "why": t("why.riegel")})
    return res


def fussriegel_einsetzen(S: Sortiment, ms: list[Bauteil], ax: int, bad: list[dict]) -> list[Bauteil]:
    """Fußriegel zwischen benachbarten Beinen in Richtung ax einsetzen."""
    o = 1 - ax
    prof = naechstes_kantholz(S, 44, 74)
    added: list[Bauteil] = []
    schlecht = [b["v"] for b in bad]
    verts = schlecht + [m for m in ms if m.long == 2 and m.min[2] <= 0.5 and ext(m, 2) > 120 and not any(v is m for v in schlecht)]
    rows: list[list[Bauteil]] = []
    for v in verts:
        r = next((r for r in rows if abs(cen(r[0], o) - cen(v, o)) < 60), None)
        if r is not None:
            r.append(v)
        else:
            rows.append([v])
    for row in rows:
        if not any(any(b is v for b in schlecht) for v in row):
            continue
        row.sort(key=lambda m: cen(m, ax))
        for i in range(len(row) - 1):
            a, b = row[i], row[i + 1]
            r = Bauteil(id=f"Fußriegel {AXN[ax]} {len(added) + 1}", part=f"Fußriegel {AXN[ax]}", name=t("teil.fussriegel"),
                        typ="kantholz", rolle="riegel", prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]},
                        long=ax, dax=-1, origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
            r.min[ax], r.max[ax] = a.max[ax], b.min[ax]
            if r.max[ax] - r.min[ax] < 100:
                continue
            c = (max(a.min[o], b.min[o]) + min(a.max[o], b.max[o])) / 2
            r.min[o], r.max[o] = c - prof["a"] / 2, c + prof["a"] / 2
            r.min[2], r.max[2] = 80, 80 + prof["b"]
            for _ in range(6):  # höher setzen, bis er frei ist
                if not any(depth(r, m) > 0.5 for m in ms):
                    break
                r.min[2] += prof["b"]
                r.max[2] += prof["b"]
            if not any(depth(r, m) > 0.5 for m in ms):
                ms.append(r)
                added.append(r)
    return added


def pruefen_und_reparieren(S: Sortiment, ms: list[Bauteil], groups: dict, g: dict, log: list[str], repairs: list[str]) -> None:
    ausgesteift: set[int] = set()  # Richtungen, in denen schon Fußriegel eingesetzt wurden (je Richtung höchstens einmal)
    gurtrahmen_fertig = False
    for _ in range(12):
        J = kontakte(ms)
        fixed = False

        # a) Handelslänge
        too_long = [m for m in ms if ext(m, m.long) > max(handelslaengen(S, m)) + 0.5]
        for m in too_long:
            if m.rolle not in ("verkleidung", "lehne") or m.long == 2:
                if f"lang|{m.part}" not in repairs and not any(l.startswith(m.name + ":") for l in log):
                    log.append(t("log.zu_lang", name=m.name, laenge=mm(ext(m, m.long)), max=zahl(max(handelslaengen(S, m)))))
        cuttable = [m for m in too_long if m.rolle in ("verkleidung", "lehne") and m.long != 2]

        def stoss(m: Bauteil):
            """Stelle über einem Träger, an der eine zu lange Latte gestoßen werden kann."""
            L = m.long
            mid, max_l = cen(m, L), max(handelslaengen(S, m))
            backs = [(j["b"] if j["a"] is m else j["a"]) for j in J
                     if (j["a"] is m or j["b"] is m) and j["ax"] != L and j["ax"] != 2]
            cut = None
            for o in backs:
                s0 = max(m.min[L], o.min[L]) + 20
                e0 = min(m.max[L], o.max[L]) - 20
                if e0 < s0:
                    continue
                c = min(max(mid, s0), e0)
                if c - m.min[L] <= max_l and m.max[L] - c <= max_l and (cut is None or abs(c - mid) < abs(cut - mid)):
                    cut = c
            return cut

        # fehlende Mittelpfosten je Gruppe
        for part in einmalig(m.part for m in cuttable if stoss(m) is None):
            name = f"Mittelpfosten {part}"
            if any(o.part == name for o in ms):
                continue
            grp = [o for o in ms if o.part == part]
            m = grp[0]
            L = m.long
            side = next(a for a in others(L) if a != 2)
            backs = [(j["b"] if j["a"] in grp else j["a"]) for j in J
                     if (j["a"] in grp or j["b"] in grp) and j["ax"] == side]
            if not backs:
                log.append(t("log.kein_traeger", name=m.name))
                continue
            behind_max = backs[0].min[side] >= m.max[side] - 1  # Träger liegen auf der max-Seite
            prof = naechstes_kantholz(S, 44, 44)
            q = prof["a"]
            tpl = Bauteil(typ="kantholz", rolle="pfosten", prof={"label": prof["label"], "a": q, "b": prof["b"]},
                          min=[0, 0, 0], max=[0, 0, 0])
            tpl.min[side] = m.max[side] if behind_max else m.min[side] - prof["b"]
            tpl.max[side] = tpl.min[side] + prof["b"]
            tpl.min[2], tpl.max[2] = 0, max(o.max[2] for o in grp)
            tpl.min[L], tpl.max[L] = 0, q
            n = senkrecht_einsetzen(ms, tpl, cen(m, L), L, name, t("teil.mittelpfosten", part=part))
            stuecke = t("rep.stuecke", n=n) if n > 1 else ""
            repairs.append(t("rep.mittelpfosten", rolle=rollenname(m.rolle), name=zitat(m.name), laenge=mm(ext(m, L)),
                             max=zahl(max(handelslaengen(S, m))), stuecke=stuecke))
            fixed = True
        if fixed:
            setzen(ms, log)
            continue
        J = kontakte(ms)
        done: set = set()
        for m in cuttable:
            cut = stoss(m)
            if cut is None:
                continue
            L = m.long
            a, b = m.kopie(id=m.id + "a"), m.kopie(id=m.id + "b")
            a.max[L] = cut
            b.min[L] = cut
            i = ms.index(m)
            ms[i:i + 1] = [a, b]
            if m.part not in done:
                done.add(m.part)
                repairs.append(t("rep.stoss", rolle=rollenname(m.rolle), name=zitat(m.name), a=mm(cut - m.min[L]),
                                 b=mm(m.max[L] - cut)))
            fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # a2) Liegefläche frei halten
        fn = g.get("funktion") or {}
        an = (g.get("anker") or {}).get("liegeflaeche")
        if gesetzt(fn.get("matratze")) and gesetzt(an):
            slats = [m for m in ms if m.rolle in SLATS]
            if slats:
                top = max(m.max[2] for m in slats)
                bb = [[min(m.min[a] for m in ms), max(m.max[a] for m in ms)] for a in (0, 1)]
                c = [bb[0][0] + (an[0] + an[1]) / 2 * (bb[0][1] - bb[0][0]),
                     bb[1][0] + (an[2] + an[3]) / 2 * (bb[1][1] - bb[1][0])]
                x_long = (an[1] - an[0]) * (bb[0][1] - bb[0][0]) >= (an[3] - an[2]) * (bb[1][1] - bb[1][0])
                mat = [max(fn["matratze"]), min(fn["matratze"])] if x_long else [min(fn["matratze"]), max(fn["matratze"])]
                zone = quader([c[0] - mat[0] / 2, c[1] - mat[1] / 2, top + 0.5], [c[0] + mat[0] / 2, c[1] + mat[1] / 2, top + 150])
                hit = [m for m in ms if m.long == 2 and depth(m, zone) > 0.5 and m.max[2] - top < 60]
                if hit:
                    over = max(m.max[2] - top for m in hit)
                    for m in hit:
                        m.max[2] = top
                    repairs.append(t("rep.liegeflaeche", teile=und(einmalig(m.name for m in hit)), over=mm(over), top=mm(top)))
                    fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # b) Lattenabstand beim Lattenrost
        for pid, gr in eintraege(groups):
            ps = [m for m in ms if m.part == pid]
            if not ps or ps[0].rolle != "lattenrost" or len(ps) < 2:
                continue
            ax = gr["dax"]
            ps.sort(key=lambda p: p.min[ax])
            dicke = ext(ps[0], ax)
            span = ps[-1].max[ax] - ps[0].min[ax]
            gap = (span - len(ps) * dicke) / (len(ps) - 1)
            if gap <= 60:
                continue
            n = math.ceil((span + 60) / (dicke + 60))
            start = ps[0].min[ax]
            fresh = []
            for i in range(n):
                m = ps[0].kopie(id=f"{pid}-{i + 1}")
                m.min[ax] = start + i * (span - dicke) / (n - 1)
                m.max[ax] = m.min[ax] + dicke
                fresh.append(m)
            for p in ps:
                ms.remove(p)
            ms.extend(fresh)
            gr["n"] = n
            repairs.append(t("rep.lattenabstand", gap=mm(gap), n=n, alt=len(ps), neu=mm((span - n * dicke) / (n - 1))))
            fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # c0) Flächen, die nirgends aufliegen: Auflageleisten an den Nachbarkanten
        J = kontakte(ms)
        for m in ms:  # wächst während der Schleife, neue Leisten werden mit durchlaufen (und übersprungen)
            if m.rolle not in SLATS or m.long == 2 or any(j["a"] is m or j["b"] is m for j in J) or m.min[2] < 30:
                continue
            lat = S["latte"][0]
            cw, ch = lat["a"], lat["b"]
            added = []
            for ax in (0, 1):
                o2 = 1 - ax
                for side in ("min", "max"):
                    edge = m.min[ax] if side == "min" else m.max[ax]
                    carrier = next((o for o in ms if o is not m and prio(o) >= 4
                                    and abs((o.max[ax] if side == "min" else o.min[ax]) - edge) <= 1.5
                                    and o.max[2] <= m.min[2] + 1 and o.max[2] >= m.min[2] - 60 and ov(m, o, o2) >= 50), None)
                    if carrier is None:
                        continue
                    c = Bauteil(id=f"Auflageleiste {m.part} {AXN[ax]}{side}", part=f"Auflageleiste {m.part}",
                                name=t("teil.auflageleiste"), typ="latte", rolle="auflage",
                                prof={"label": lat["label"], "a": lat["a"], "b": lat["b"]}, long=o2, dax=-1,
                                origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
                    c.min[o2], c.max[o2] = max(m.min[o2], carrier.min[o2]), min(m.max[o2], carrier.max[o2])
                    c.min[ax] = edge if side == "min" else edge - cw
                    c.max[ax] = c.min[ax] + cw
                    c.max[2], c.min[2] = m.min[2], m.min[2] - ch
                    if not any(depth(c, o) > 0.5 for o in ms):
                        ms.append(c)
                        added.append(c)
            if added:
                repairs.append(t("rep.auflage", name=m.name, n=len(added), holz=holz(lat["label"])))
                fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # c0) Gurtsitz: Rahmen rundum schließen (einmal)
        if not gurtrahmen_fertig:
            gurtrahmen_fertig = True
            for name in gurtrahmen(S, ms):
                repairs.append(t("rep.gurtrahmen", name=name))
                fixed = True
            if fixed:
                setzen(ms, log)
                continue

        # c1) Liegende Teile, deren eines Ende neben einem Bein in der Luft hängt (z. B. Armlehne neben dem Vorderbein,
        # weil sie dem Pfosten ausweichen musste): breiter machen, damit sie auf dem Bein liegt, und vor dem Pfosten enden
        J = kontakte(ms)
        gemeldet = set()
        for m in ms:
            if _auf_bein_legen(ms, m, J):
                if m.part not in gemeldet:
                    repairs.append(t("rep.auf_bein", name=m.name))
                    gemeldet.add(m.part)
                fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # c) Spannweiten
        J = kontakte(ms)
        for m in ms:
            gurt = m.rolle == "gurt"
            if (m.rolle not in LOADED and not gurt) or m.long == 2:
                continue
            si = spannweite(m, J)
            if gurt and si["supported"] and not (si["worst"].get("cant") and si["worst"]["len"] > 2 * GURT_FREI):
                continue  # Gurte federn: Spannweite egal, nur beide Enden müssen auf einem Holz liegen
            if gurt and _gurte_verlaengern(ms, m):
                repairs.append(t("rep.gurt_laenger", name=m.name))
                fixed = True
                break
            if not si["supported"] or gurt:
                # Latten, die nirgends aufliegen (z. B. zu kurz gelesen): zwei Querriegel unter die Enden der Reihe
                name = f"Querriegel {m.part}"
                if (m.rolle in SLATS or gurt) and m.part in groups and m.min[2] > 30 and not any(o.part == name for o in ms):
                    ps = [o for o in ms if o.part == m.part]
                    dax, L = groups[m.part]["dax"], m.long
                    prof = naechstes_kantholz(S, 44, 74)
                    for i, at in enumerate((m.min[L] + prof["a"], m.max[L] - prof["a"])):
                        q = Bauteil(id=f"{name} {i + 1}", part=name, name=t("teil.querriegel"), typ="kantholz",
                                    rolle="querriegel", prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]},
                                    long=dax, dax=-1, origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
                        q.min[dax], q.max[dax] = min(o.min[dax] for o in ps), max(o.max[dax] for o in ps)
                        q.min[L], q.max[L] = at - prof["a"] / 2, at + prof["a"] / 2
                        q.max[2], q.min[2] = m.min[2], m.min[2] - prof["b"]
                        ms.append(q)
                        kuerzen(ms, q)
                    repairs.append(t("rep.unterstuetzt", name=m.name, holz=holz(prof["label"])))
                    fixed = True
                    break
                # eingefügter Steg, der selbst nirgends aufliegt: Stützen bis zum Boden unter beide Enden
                name = f"Stütze {m.id}"
                if m.origin == "reparatur" and m.rolle in ("mittelsteg", "querriegel") and m.min[2] > 30 \
                        and not any(o.part == name for o in ms):
                    prof = naechstes_kantholz(S, 44, 44)
                    L = m.long
                    o_ax = next(a for a in others(2) if a != L)
                    for i, at in enumerate((m.min[L] + prof["a"], m.max[L] - prof["a"])):
                        tpl = Bauteil(typ="kantholz", rolle="stuetze",
                                      prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]},
                                      min=[0, 0, 0], max=[0, 0, 0])
                        tpl.min[L], tpl.max[L] = 0, prof["a"]
                        tpl.min[o_ax], tpl.max[o_ax] = cen(m, o_ax) - prof["b"] / 2, cen(m, o_ax) + prof["b"] / 2
                        tpl.min[2], tpl.max[2] = 0, m.min[2]
                        senkrecht_einsetzen(ms, tpl, at, L, f"{name} {i + 1}", t("teil.stuetze", id=m.id))
                    repairs.append(t("rep.steg_stuetzen", name=m.name))
                    fixed = True
                    break
                continue
            krag = bool(si["worst"].get("cant"))
            lm = max_spannweite(m, ms, J, g, krag)
            if si["worst"]["len"] <= lm:
                continue
            L = m.long
            # zuerst stärkeres Holz (sieht aus wie im Entwurf), sonst Mittelsteg bzw. Stütze
            alt = holz(m.prof["label"]) if "label" in m.prof else t("plan.brett", t=zahl(m.prof.get("t", 0)),
                                                                     w=zahl(m.prof.get("w", 0)))
            # Welche Lösung braucht weniger Holz: stärkeres Holz für die ganze Gruppe oder ein Steg / eine Stütze?
            mehr_holz = staerker_machen(S, ms, m, si["worst"]["len"], J, g, krag, nur_volumen=True)
            steg_holz = _steg_volumen(S, ms, groups, m, si["worst"]["len"], lm)
            neu = None
            immer_staerker = g.get("_reparatur") == "staerker"  # zweiter Durchgang der Engine, siehe berechnen()
            if mehr_holz is not None and (immer_staerker or steg_holz is None or mehr_holz <= steg_holz):
                neu = staerker_machen(S, ms, m, si["worst"]["len"], J, g, krag)
            if neu:
                repairs.append(t("rep.staerker", name=m.name, len=mm(si["worst"]["len"]), alt=alt, neu=neu))
                fixed = True
                break
            if m.rolle in SLATS and m.part in groups:
                name = f"Mittelsteg {m.part}"
                if any(o.part == name for o in ms):
                    continue
                ps = [o for o in ms if o.part == m.part]
                dax = groups[m.part]["dax"]
                prof = naechstes_kantholz(S, 44, 74)
                rost = m.rolle == "lattenrost"
                # so viele Stege, dass jedes Feld kürzer als erlaubt ist (lange, gestreckte Möbel brauchen mehrere)
                laenge = si["worst"]["len"]
                k = max(1, min(8, math.ceil(laenge / lm) - 1))
                anfang = si["worst"]["at"] - laenge / 2
                for i in range(k):
                    at = si["worst"]["at"] if k == 1 else anfang + (i + 1) * laenge / (k + 1)
                    s = Bauteil(id=name if i == 0 else f"{name} {i + 1}", part=name,
                                name=t("teil.mittelsteg") if rost else t("teil.querriegel"), typ="kantholz",
                                rolle="mittelsteg" if rost else "querriegel",
                                prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]}, long=dax, dax=-1,
                                origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
                    s.min[dax], s.max[dax] = min(p.min[dax] for p in ps), max(p.max[dax] for p in ps)
                    s.min[L], s.max[L] = at - prof["a"] / 2, at + prof["a"] / 2
                    s.max[2], s.min[2] = m.min[2], m.min[2] - prof["b"]
                    ms.append(s)
                    kuerzen(ms, s)
                repairs.append(t("rep.mittelsteg" if k == 1 else "rep.mittelstege", rolle=rollenname(m.rolle),
                                 len=mm(laenge), lm=mm(lm), h=mm(ext(m, 2)), steg=s.name, holz=holz(prof["label"]), n=k))
                fixed = True
                break
            if m.min[2] > 30:
                name = f"Stütze {m.id}"  # je Teil, nicht je Gruppe: zwei Holme brauchen zwei Stützen
                if any(o.part == name for o in ms):
                    continue
                prof = naechstes_kantholz(S, 44, 44)
                tpl = Bauteil(typ="kantholz", rolle="stuetze", prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]},
                              min=[0, 0, 0], max=[0, 0, 0])
                o = next(a for a in others(2) if a != L)
                tpl.min[L], tpl.max[L] = 0, prof["a"]
                tpl.min[o], tpl.max[o] = cen(m, o) - prof["b"] / 2, cen(m, o) + prof["b"] / 2
                tpl.min[2], tpl.max[2] = 0, m.min[2]
                senkrecht_einsetzen(ms, tpl, si["worst"]["at"], L, name, t("teil.stuetze", id=m.id))
                repairs.append(t("rep.stuetze", name=m.name, len=mm(si["worst"]["len"]), lm=mm(lm), h=mm(ext(m, 2))))
                fixed = True
                break
        if fixed:
            setzen(ms, log)
            continue

        # d) Aussteifung (je Richtung höchstens einmal)
        J = kontakte(ms)
        for b in aussteifung(ms, J):
            if b["ok"] or b["ax"] in ausgesteift:
                continue
            added = fussriegel_einsetzen(S, ms, b["ax"], b["bad"])
            if added:
                ausgesteift.add(b["ax"])
                richtung = t("rep.wackelt_x") if b["ax"] == 0 else t("rep.wackelt_y")
                repairs.append(t("rep.wackelt", richtung=richtung, why=b["bad"][0]["why"], n=len(added),
                                 holz=holz(added[0].prof["label"])))
                fixed = True
        if fixed:
            setzen(ms, log)
            continue
        break
