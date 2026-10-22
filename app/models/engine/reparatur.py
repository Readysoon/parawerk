"""Schritt 4: Prüfen und reparieren.

Reihenfolge je Durchlauf: Handelslänge, Liegefläche frei, Lattenabstand, fehlende Auflager, Spannweiten,
Aussteifung. Nach jeder Reparatur werden die Teile neu gesetzt und es geht von vorn los (höchstens 8-mal).
"""
from __future__ import annotations

import math

from ..sortiment import Sortiment, handelslaengen, naechstes_kantholz
from .grundlagen import (
    ATTACH, AXN, LOADED, SLATS, Bauteil, cen, depth, einmalig, eintraege, ext, gesetzt, mm, others, ov, prio,
    quader, rollenname, zahl,
)
from .setzen import kontakte, setzen


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
        elif m.rolle not in SLATS:
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


def max_spannweite(m: Bauteil) -> float:
    """Faustregel: Latten und Bretter 40 × Stärke, tragende Hölzer 25 × Höhe, Leimholzböden höchstens 800 mm."""
    h = ext(m, 2)
    k = 40 if m.rolle in SLATS else 25
    return min(800, k * h) if m.typ == "brett" and m.rolle == "regalboden" else k * h


def senkrecht_einsetzen(ms: list[Bauteil], tpl: Bauteil, at: float, along: int, label: str) -> int:
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
        m = tpl.kopie(id=f"{label}-{k}" if len(segs) > 1 else label, part=label, name=label, origin="reparatur",
                      long=2, dax=-1)
        m.min, m.max = list(base.min), list(base.max)
        m.min[2], m.max[2] = z0, z1
        ms.append(m)
    return len(segs)


def aussteifung(ms: list[Bauteil], J: list[dict]) -> list[dict]:
    """Je Richtung (x = von vorne gesehen, y = von der Seite) prüfen, ob das Gestell gegen Verschieben gesichert ist."""
    if any(m.rolle == "wandleiste" for m in ms):
        return [{"ax": 0, "ok": True, "why": "Wandbefestigung"}, {"ax": 1, "ok": True, "why": "Wandbefestigung"}]
    bb = [[min(m.min[a] for m in ms), max(m.max[a] for m in ms)] for a in (0, 1)]

    def am_rand(v: Bauteil, a: int) -> bool:
        spanne = bb[a][1] - bb[a][0]
        return cen(v, a) - bb[a][0] < 0.25 * spanne or bb[a][1] - cen(v, a) < 0.25 * spanne

    verts = [m for m in ms if m.long == 2 and m.min[2] <= 0.5 and ext(m, 2) > 120 and am_rand(m, 0) and am_rand(m, 1)]
    res = []
    for ax in (0, 1):
        if len(verts) < 2:
            res.append({"ax": ax, "ok": True, "why": "keine hohen Beine (liegt flächig auf)"})
            continue
        o = 1 - ax
        # Platte oder Verkleidung in dieser Ebene, die mindestens zwei Beine verbindet
        sheet = next((m for m in ms if m.typ == "brett" and ext(m, ax) >= 300 and ext(m, 2) >= 200 and ext(m, o) <= 30
                      and sum(1 for v in verts if _beruehrt(J, m, v)) >= 2), None)
        if sheet is not None:
            res.append({"ax": ax, "ok": True, "why": f"{sheet.name} steift aus"})
            continue
        clad = [m for m in ms if m.rolle in ("verkleidung", "lehne") and m.long == ax
                and sum(1 for v in verts if _beruehrt(J, m, v)) >= 2]
        if len(clad) >= 3:
            res.append({"ax": ax, "ok": True, "why": f"{len(clad)} verschraubte {rollenname(clad[0].rolle)}-Latten steifen aus"})
            continue
        vclad = [m for m in ms if m.rolle in ("verkleidung", "lehne") and m.long == 2 and ext(m, o) <= 30
                 and sum(1 for h in ms if h is not m and h.long != 2 and prio(h) >= 3 and _beruehrt(J, h, m)) >= 2]
        if len(vclad) >= 3:
            res.append({"ax": ax, "ok": True, "why": f"{len(vclad)} senkrechte, oben und unten verschraubte Latten steifen aus"})
            continue
        # je Bein: Riegel in Richtung ax, ihre Höhen und die freie Beinlänge
        bad = []
        for v in verts:
            rails = [m for m in ms if m is not v and m.long != 2 and prio(m) >= 3 and _beruehrt(J, m, v)
                     and (m.long == ax or ext(m, 2) >= 70)]
            if not rails:
                bad.append({"v": v, "why": "kein Riegel"})
                continue
            zs = sorted(([r.min[2], r.max[2]] for r in rails), key=lambda p: p[0])
            spread = zs[-1][0] - zs[0][1]
            free = zs[0][0]
            tiefe = max(ext(r, 2) for r in rails)
            if spread >= 0.25 * ext(v, 2):
                continue  # zwei Riegelebenen
            if free <= 450 and tiefe >= 70:
                continue  # kurze Beine an breiter Zarge
            bad.append({"v": v, "why": f"freie Beinlänge {mm(free)} mm"})
        res.append({"ax": ax, "ok": False, "bad": bad} if bad
                   else {"ax": ax, "ok": True, "why": "Riegel auf zwei Höhen oder kurze Beine an breiter Zarge"})
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
            r = Bauteil(id=f"Fußriegel {AXN[ax]} {len(added) + 1}", part=f"Fußriegel {AXN[ax]}", name="Fußriegel",
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
    for _ in range(8):
        J = kontakte(ms)
        fixed = False

        # a) Handelslänge
        too_long = [m for m in ms if ext(m, m.long) > max(handelslaengen(S, m)) + 0.5]
        for m in too_long:
            if m.rolle not in ("verkleidung", "lehne") or m.long == 2:
                if f"lang|{m.part}" not in repairs and not any(l.startswith(m.name + ":") for l in log):
                    log.append(f"{m.name}: {mm(ext(m, m.long))} mm ist länger als die längste Handelslänge "
                               f"({zahl(max(handelslaengen(S, m)))} mm). Stoß über einer Auflage nötig.")
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
                log.append(f"{m.name}: zu lang und nichts dahinter, woran ein Mittelpfosten befestigt werden könnte.")
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
            n = senkrecht_einsetzen(ms, tpl, cen(m, L), L, name)
            stuecke = f" (in {n} Stücken, weil er an anderen Teilen vorbeiläuft)" if n > 1 else ""
            repairs.append(f"{rollenname(m.rolle)} „{m.name}“ ist {mm(ext(m, L))} mm lang, Latten gibt es nur bis "
                           f"{zahl(max(handelslaengen(S, m)))} mm: Mittelpfosten eingefügt{stuecke}.")
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
                repairs.append(f"{rollenname(m.rolle)} „{m.name}“: Latten werden {mm(cut - m.min[L])} + "
                               f"{mm(m.max[L] - cut)} mm lang und auf einem Pfosten gestoßen.")
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
                    teile = " und ".join(einmalig(m.name for m in hit))
                    repairs.append(f"{teile} ragen {mm(over)} mm über den Lattenrost in die Matratzenfläche: "
                                   f"auf Höhe Lattenrost ({mm(top)} mm) gekürzt.")
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
            t = ext(ps[0], ax)
            span = ps[-1].max[ax] - ps[0].min[ax]
            gap = (span - len(ps) * t) / (len(ps) - 1)
            if gap <= 60:
                continue
            n = math.ceil((span + 60) / (t + 60))
            start = ps[0].min[ax]
            fresh = []
            for i in range(n):
                m = ps[0].kopie(id=f"{pid}-{i + 1}")
                m.min[ax] = start + i * (span - t) / (n - 1)
                m.max[ax] = m.min[ax] + t
                fresh.append(m)
            for p in ps:
                ms.remove(p)
            ms.extend(fresh)
            gr["n"] = n
            repairs.append(f"Lattenrost: Abstand {mm(gap)} mm ist zu groß für eine Matratze (Richtwert max. 60 mm). "
                           f"{n} statt {len(ps)} Latten, Abstand jetzt {mm((span - n * t) / (n - 1))} mm.")
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
                                name="Auflageleiste", typ="latte", rolle="auflage",
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
                repairs.append(f"{m.name} liegt nirgends auf: {len(added)} Auflageleisten ({lat['label']}) an den Rahmenteilen ergänzt.")
                fixed = True
        if fixed:
            setzen(ms, log)
            continue

        # c) Spannweiten
        J = kontakte(ms)
        for m in ms:
            if m.rolle not in LOADED or m.long == 2:
                continue
            si, lm = spannweite(m, J), max_spannweite(m)
            if not si["supported"] or si["worst"]["len"] <= lm:
                continue
            L = m.long
            if m.rolle in SLATS and m.part in groups:
                name = f"Mittelsteg {m.part}"
                if any(o.part == name for o in ms):
                    continue
                ps = [o for o in ms if o.part == m.part]
                dax = groups[m.part]["dax"]
                prof = naechstes_kantholz(S, 44, 74)
                rost = m.rolle == "lattenrost"
                s = Bauteil(id=name, part=name, name="Mittelsteg" if rost else "Querriegel", typ="kantholz",
                            rolle="mittelsteg" if rost else "querriegel",
                            prof={"label": prof["label"], "a": prof["a"], "b": prof["b"]}, long=dax, dax=-1,
                            origin="reparatur", min=[0, 0, 0], max=[0, 0, 0])
                s.min[dax], s.max[dax] = min(p.min[dax] for p in ps), max(p.max[dax] for p in ps)
                s.min[L], s.max[L] = si["worst"]["at"] - prof["a"] / 2, si["worst"]["at"] + prof["a"] / 2
                s.max[2], s.min[2] = m.min[2], m.min[2] - prof["b"]
                ms.append(s)
                repairs.append(f"{rollenname(m.rolle)}: freie Spannweite {mm(si['worst']['len'])} mm, erlaubt ca. {mm(lm)} mm "
                               f"bei {mm(ext(m, 2))} mm Stärke. {s.name} ({prof['label']}) in der Mitte darunter eingefügt.")
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
                senkrecht_einsetzen(ms, tpl, si["worst"]["at"], L, name)
                repairs.append(f"{m.name}: freie Spannweite {mm(si['worst']['len'])} mm, erlaubt ca. {mm(lm)} mm bei "
                               f"{mm(ext(m, 2))} mm Höhe. Stütze bis zum Boden eingefügt.")
                fixed = True
                break
        if fixed:
            setzen(ms, log)
            continue

        # d) Aussteifung (je Richtung höchstens einmal)
        J = kontakte(ms)
        for b in aussteifung(ms, J):
            richtung = "seitlich" if b["ax"] == 0 else "nach vorne"
            if b["ok"] or any(r.startswith(f"Gestell wackelt {richtung}") for r in repairs):
                continue
            added = fussriegel_einsetzen(S, ms, b["ax"], b["bad"])
            if added:
                lang = "seitlich (von vorne gesehen)" if b["ax"] == 0 else "nach vorne/hinten (von der Seite gesehen)"
                repairs.append(f"Gestell wackelt {lang}: {b['bad'][0]['why']}. {len(added)} Fußriegel ({added[0].prof['label']}) eingefügt.")
                fixed = True
        if fixed:
            setzen(ms, log)
            continue
        break
