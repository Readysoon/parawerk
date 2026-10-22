"""Schritt 3: Teile aneinandersetzen.

Die Bildlesung ist ungenau. Hier werden Überschneidungen aufgelöst, kleine Fugen geschlossen, Enden an ihre
Auflager verlängert, Leisten angelegt und Flächen auf ihr Auflager abgesenkt.
"""
from __future__ import annotations

from .grundlagen import (
    ATTACH, GAP, GRAVITY, TOL, Bauteil, cen, depth, mm, others, ov, pen_sum, prio, quader, seite, touches,
)


def _merke(stats: dict, m: Bauteil, betrag: float) -> None:
    stats.setdefault("ids", set()).add(m.id)
    stats["max"] = max(stats["max"], betrag)


def enden_anschliessen(ms: list[Bauteil], stats: dict) -> None:
    """Enden bis an das nächste tragende Teil verlängern oder kürzen; Senkrechtes auf den Boden stellen."""
    for m in sorted(ms, key=prio):
        L = m.long
        c1, c2 = others(L)
        for side in ("min", "max"):
            if L == 2 and side == "min" and m.min[2] <= TOL:
                if m.min[2] != 0:
                    _merke(stats, m, m.min[2])
                    m.min[2] = 0
                continue
            if any(o is not m and o.part != m.part and touches(m, o, L, side) for o in ms):
                continue  # Ende sitzt schon an
            best = None
            for o in ms:
                if o is m or prio(o) < prio(m) or o.part == m.part:
                    continue
                if ov(m, o, c1) <= 2 or ov(m, o, c2) <= 2:
                    continue
                if side == "min":
                    if o.min[L] >= m.min[L] or o.max[L] >= m.max[L]:
                        continue
                    d = o.max[L] - m.min[L]
                else:
                    if o.max[L] <= m.max[L] or o.min[L] <= m.min[L]:
                        continue
                    d = o.min[L] - m.max[L]
                if abs(d) > TOL or (best and abs(d) >= abs(best)):
                    continue
                # Verlängerung darf durch nichts anderes hindurchgehen
                probe = quader(m.min, m.max)
                seite(probe, side)[L] = seite(m, side)[L] + d
                if any(q is not m and q is not o and q.part != m.part and depth(probe, q) > depth(m, q) + 0.5 for q in ms):
                    continue
                best = d
            if best is not None and abs(best) > 0.4:
                seite(m, side)[L] += best
                _merke(stats, m, abs(best))


def anlegen(ms: list[Bauteil], stats: dict) -> None:
    """Leisten, Lehnen und Verkleidung seitlich an ihren Träger anlegen."""
    for m in ms:
        if m.rolle not in ATTACH:
            continue
        best = None
        fertig = False
        for ax in others(m.long):
            for o in ms:
                if o is m or o.part == m.part or prio(o) <= prio(m):
                    continue
                p, q = others(ax)
                if ov(m, o, p) < 5 or ov(m, o, q) < 5:
                    continue
                for side in ("min", "max"):
                    if touches(m, o, ax, side):
                        best = {"d": 0}
                        break
                    d = o.max[ax] - m.min[ax] if side == "min" else o.min[ax] - m.max[ax]
                    if (side == "min" and d > 0) or (side == "max" and d < 0):
                        continue  # o liegt auf der falschen Seite
                    if abs(d) <= TOL and (best is None or abs(d) < abs(best["d"])):
                        best = {"d": d, "ax": ax}
                if best is not None and best["d"] == 0:
                    fertig = True
                    break
            if fertig:
                break
        if best is not None and best["d"] and abs(best["d"]) > 0.4:
            ax = best["ax"]
            probe = quader(m.min, m.max)
            probe.min[ax] += best["d"]
            probe.max[ax] += best["d"]
            if pen_sum(probe, [o for o in ms if o is not m]) <= pen_sum(m, ms) + 0.5:
                m.min[ax] += best["d"]
                m.max[ax] += best["d"]
                _merke(stats, m, abs(best["d"]))


def fugen_schliessen(ms: list[Bauteil], stats: dict) -> None:
    """Kleine Fugen aus der ungenauen Bildlesung schließen (bis 12 mm); das schwächere Teil bewegt sich."""
    for _ in range(3):
        moved = False
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = ms[i], ms[j]
                if a.part == b.part:
                    continue
                for ax in (0, 1, 2):
                    p, q = others(ax)
                    if ov(a, b, p) < 5 or ov(a, b, q) < 5:
                        continue
                    g1, g2 = b.min[ax] - a.max[ax], a.min[ax] - b.max[ax]
                    gap = g1 if g1 > 0 else g2 if g2 > 0 else 0
                    if gap <= 0.5 or gap > GAP:
                        continue
                    a_below = g1 > 0  # a liegt auf der kleineren Seite
                    order = [a, b] if prio(a) < prio(b) else [b, a]
                    for mv in order:
                        if ax == 2 and mv.min[2] <= 0.5:
                            continue  # nichts vom Boden abheben
                        s = gap if (mv is a) == a_below else -gap
                        probe = quader(mv.min, mv.max)
                        probe.min[ax] += s
                        probe.max[ax] += s
                        rest = [o for o in ms if o is not mv and o.part != mv.part]
                        if pen_sum(probe, rest) > pen_sum(mv, rest) + 0.5:
                            continue
                        mv.min[ax] += s
                        mv.max[ax] += s
                        _merke(stats, mv, gap)
                        moved = True
                        break
                    break
        if not moved:
            break


def absenken(ms: list[Bauteil], stats: dict) -> None:
    """Latten und Böden auf das nächste Teil darunter legen."""
    for m in ms:
        if m.long == 2 or m.rolle not in GRAVITY or m.min[2] < 0.5:
            continue
        best = None
        for o in ms:
            if o is m or o.part == m.part or ov(m, o, 0) <= 2 or ov(m, o, 1) <= 2 or o.min[2] >= m.min[2]:
                continue
            d = o.max[2] - m.min[2]
            if abs(d) <= TOL and (best is None or abs(d) < abs(best)):
                best = d
        if best is not None and abs(best) > 0.4:
            m.min[2] += best
            m.max[2] += best
            _merke(stats, m, abs(best))


def _anwenden(c: dict, ziel: Bauteil) -> None:
    ax = c["ax"]
    if c["kind"] == "move":
        ziel.min[ax] += c["dir"] * c["amt"]
        ziel.max[ax] += c["dir"] * c["amt"]
    elif c["at_min"]:
        ziel.min[ax] = c["other"].max[ax]
    else:
        ziel.max[ax] = c["other"].min[ax]


def ueberschneidungen_loesen(ms: list[Bauteil], log: list[str]) -> None:
    """Für jede Überschneidung mehrere Korrekturen probieren und die mit den wenigsten Folgekollisionen nehmen."""
    gemeldet: set[str] = set()
    for _ in range(6):
        changed = False
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = ms[i], ms[j]
                if not depth(a, b):
                    continue
                lo = a if prio(a) < prio(b) else b
                hi = b if lo is a else a
                cands = []
                for mv, other, pen in ((lo, hi, 0), (hi, lo, 30)):
                    for ax in (0, 1, 2):
                        for richtung in (-1, 1):
                            amt = mv.max[ax] - other.min[ax] if richtung < 0 else other.max[ax] - mv.min[ax]
                            if amt > TOL or amt <= 0:
                                continue
                            cands.append({"mv": mv, "ax": ax, "kind": "move", "amt": amt, "penalty": pen, "dir": richtung})
                        if ax == mv.long and (other.min[ax] <= mv.min[ax] + 1 or other.max[ax] >= mv.max[ax] - 1):
                            at_min = cen(other, ax) < cen(mv, ax)
                            amt = other.max[ax] - mv.min[ax] if at_min else mv.max[ax] - other.min[ax]
                            if 0 < amt <= TOL:
                                strafe = pen + (2 * amt + 10 if prio(mv) >= 5 else 5)
                                cands.append({"mv": mv, "ax": ax, "kind": "cut", "amt": amt, "penalty": strafe,
                                              "at_min": at_min, "other": other})
                best = None
                for c in cands:
                    probe = quader(c["mv"].min, c["mv"].max)
                    _anwenden(c, probe)
                    partner = hi if c["mv"] is lo else lo
                    rest = [o for o in ms if o is not c["mv"] and o is not partner]
                    added = 0
                    for o in rest:
                        added = added + max(0, depth(probe, o) - depth(c["mv"], o))
                    added = added + depth(probe, partner)
                    score = added * 1000 + c["amt"] + c["penalty"]
                    if best is None or score < best["score"]:
                        best = {**c, "score": score}
                if best is None:
                    k = f"{lo.part}|{hi.part}"
                    if k not in gemeldet:
                        gemeldet.add(k)
                        log.append(f"Konflikt: {lo.name} und {hi.name} überschneiden sich stark. Im Entwurf unklar, bitte prüfen.")
                    continue
                _anwenden(best, best["mv"])
                changed = True
        if not changed:
            break


def setzen(ms: list[Bauteil], log: list[str]) -> dict:
    stats = {"n": 0, "max": 0}
    ueberschneidungen_loesen(ms, log)
    fugen_schliessen(ms, stats)
    enden_anschliessen(ms, stats)
    anlegen(ms, stats)
    absenken(ms, stats)
    ueberschneidungen_loesen(ms, log)
    fugen_schliessen(ms, stats)
    enden_anschliessen(ms, stats)
    return stats


def kontakte(ms: list[Bauteil]) -> list[dict]:
    """Alle Berührungen (Verbindungsstellen) zwischen zwei Teilen."""
    J = []
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a, b = ms[i], ms[j]
            for ax in (0, 1, 2):
                g1, g2 = b.min[ax] - a.max[ax], a.min[ax] - b.max[ax]
                g = g1 if abs(g1) < abs(g2) else g2
                if g < -0.6 or g > 1.5:
                    continue
                o1, o2 = others(ax)
                if ov(a, b, o1) >= 5 and ov(a, b, o2) >= 5:
                    J.append({"a": a, "b": b, "ax": ax})
                    break
    return J


__all__ = ["setzen", "kontakte", "mm"]
