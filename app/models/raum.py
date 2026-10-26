"""Raummaße aus einem Foto: Tiefenkarte + eine echte Messung → Breite, Tiefe, Höhe des markierten Bereichs.

Ein Tiefenmodell (z. B. Depth Pro) schätzt für jeden Bildpunkt die Entfernung zur Kamera. Den genauen Maßstab
kennt es nicht sicher, darum misst der Nutzer eine Strecke im Foto nach (z. B. „Nische 185 cm“). Damit wird
die ganze Tiefenkarte skaliert. Bei zwei Messungen zeigt der Vergleich, ob die Rechnung stimmt.

Koordinaten: Kamera schaut entlang +z, x nach rechts, y nach unten (wie im Bild). Punkte im Bild sind
relativ (0–1), damit es egal ist, in welcher Größe App oder Browser das Foto zeigen.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np

MAX_SEITE = 512  # Tiefenkarte zum Rechnen und Speichern verkleinern
MIN_TIEFE_MM = 150  # weniger ist meist nur Rauschen einer Wand: dann keine Tiefe vorschlagen
MAX_TIEFE_MM = 1500  # mehr: wohl keine Wand dahinter (frei im Raum), dann lieber selbst eintragen
ABWEICHUNG_WARNUNG = 0.08  # zwei Messungen passen nicht zusammen, wenn sie mehr als 8 % abweichen


@dataclass
class Tiefe:
    """Tiefenkarte in Metern (Höhe × Breite) und Brennweite in Pixeln dieser Karte."""
    karte: np.ndarray
    brennweite: float
    flach: bool = False  # nur Ersatz (kein Tiefenmodell): Maße gelten dann nur in der Ebene der Messung

    def verkleinert(self) -> "Tiefe":
        h, w = self.karte.shape
        schritt = int(np.ceil(max(h, w) / MAX_SEITE))
        if schritt <= 1:
            return self
        return Tiefe(self.karte[::schritt, ::schritt], self.brennweite / schritt, self.flach)

    def als_bytes(self) -> bytes:
        puffer = io.BytesIO()
        np.savez_compressed(puffer, tiefe=self.karte.astype(np.float16), brennweite=np.float32(self.brennweite),
                            flach=np.bool_(self.flach))
        return puffer.getvalue()

    @classmethod
    def aus_bytes(cls, daten: bytes) -> "Tiefe":
        with np.load(io.BytesIO(daten), allow_pickle=False) as z:
            return cls(z["tiefe"].astype(np.float32), float(z["brennweite"]), bool(z["flach"]) if "flach" in z.files else False)


def flach(breite: int, hoehe: int, abstand: float = 3.0) -> Tiefe:
    """Ersatz ohne Tiefenmodell: alles gleich weit weg (wie eine Wand von vorn). Die Messung skaliert dann rein 2D."""
    return Tiefe(np.full((hoehe, breite), abstand, np.float32), 0.8 * max(breite, hoehe), flach=True).verkleinert()


@dataclass
class Messung:
    a: tuple[float, float]  # relativ (0–1)
    b: tuple[float, float]
    mm: float


@dataclass
class Masse:
    breite: int | None
    tiefe: int | None
    hoehe: int | None
    abweichung: float | None = None  # bei zwei und mehr Messungen: größter Unterschied der Maßstäbe (0.05 = 5 %)
    hinweise: list[str] = field(default_factory=list)  # i18n-Schlüssel

    @property
    def bereich(self) -> list[int | None]:
        return [self.breite, self.tiefe, self.hoehe]


def _punkte(t: Tiefe) -> np.ndarray:
    """Alle Bildpunkte als 3D-Punkte in Metern (Höhe × Breite × 3)."""
    h, w = t.karte.shape
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    z = t.karte
    return np.stack([(u - w / 2) * z / t.brennweite, (v - h / 2) * z / t.brennweite, z], axis=-1)


def _punkt(p: np.ndarray, rel: tuple[float, float]) -> np.ndarray:
    """3D-Punkt an einer Stelle im Bild, Tiefe als Median der Umgebung (robust gegen Kanten und Ausreißer)."""
    h, w, _ = p.shape
    x = min(w - 1, max(0, int(rel[0] * w)))
    y = min(h - 1, max(0, int(rel[1] * h)))
    r = max(1, round(max(h, w) / 200))
    feld = p[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].reshape(-1, 3)
    z = np.median(feld[:, 2])
    mitte = p[y, x]
    return mitte * (z / mitte[2]) if mitte[2] > 0 else mitte


def _oben(p: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float | None]:
    """Richtung „oben“ und Höhe des Bodens. Sucht den Boden als Ebene im unteren Bilddrittel (RANSAC).

    Findet sich keiner, gilt die Bildachse nach oben (Handy etwa gerade gehalten) und der Boden bleibt unbekannt.
    """
    h = p.shape[0]
    unten = p[int(h * 2 / 3):].reshape(-1, 3)
    unten = unten[np.isfinite(unten).all(1) & (unten[:, 2] > 0)]
    standard = np.array([0.0, -1.0, 0.0])
    if len(unten) < 50:
        return standard, None
    probe = unten[rng.choice(len(unten), min(len(unten), 4000), replace=False)]
    toleranz = 0.02 * float(np.median(probe[:, 2]))  # 2 % der Entfernung
    beste, beste_n = None, 0
    for _ in range(200):
        a, b, c = probe[rng.choice(len(probe), 3, replace=False)]
        n = np.cross(b - a, c - a)
        laenge = np.linalg.norm(n)
        if laenge < 1e-9:
            continue
        n = n / laenge
        if n[1] > 0:
            n = -n  # nach oben zeigen lassen (y zeigt im Bild nach unten)
        if n @ standard < np.cos(np.radians(35)):  # nur fast waagrechte Ebenen sind Boden
            continue
        anzahl = int((np.abs((probe - a) @ n) < toleranz).sum())
        if anzahl > beste_n:
            beste, beste_n = (n, float(a @ n)), anzahl
    if beste is None or beste_n < 0.3 * len(probe):
        return standard, None
    n, d = beste
    # Ebene mit allen passenden Punkten nachschärfen
    nah = probe[np.abs(probe @ n - d) < toleranz]
    if len(nah) >= 3:
        mitte = nah.mean(0)
        _, _, vt = np.linalg.svd(nah - mitte, full_matrices=False)
        n2 = vt[2] if vt[2][1] < 0 else -vt[2]
        if n2 @ standard > np.cos(np.radians(35)):
            return n2, float(mitte @ n2)
    return n, d


def massstab(t: Tiefe, messungen: list[Messung]) -> tuple[list[float], np.ndarray]:
    """Maßstab je Messung (echte mm je geschätztem mm) und die 3D-Punkte."""
    p = _punkte(t)
    faktoren = []
    for m in messungen:
        abstand = float(np.linalg.norm(_punkt(p, m.a) - _punkt(p, m.b))) * 1000
        if abstand > 1e-3:
            faktoren.append(m.mm / abstand)
    return faktoren, p


def _maske_anpassen(maske: np.ndarray, groesse: tuple[int, int]) -> np.ndarray:
    """Maske (Graustufen oder bool, beliebige Größe) als bool in Größe der Tiefenkarte (nächster Nachbar)."""
    h, w = groesse
    m = np.asarray(maske)
    if m.shape != (h, w):
        ys = (np.arange(h) * m.shape[0] / h).astype(int)
        xs = (np.arange(w) * m.shape[1] / w).astype(int)
        m = m[ys][:, xs]
    return m if m.dtype == bool else m > 127


def _waagrecht(v: np.ndarray, oben: np.ndarray) -> np.ndarray:
    """Vektoren ohne ihren senkrechten Anteil."""
    return v - np.outer(v @ oben, oben) if v.ndim == 2 else v - (v @ oben) * oben


def _gerade(punkte: np.ndarray, oben: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Richtung der Geraden mit den meisten Punkten (waagrechte Punkte in mm) und welche Punkte darauf liegen."""
    standard = _waagrecht(np.array([1.0, 0, 0]), oben)
    standard /= np.linalg.norm(standard)
    if len(punkte) < 3:
        return standard, np.ones(len(punkte), bool)
    toleranz = max(20.0, 0.01 * float(np.median(np.linalg.norm(punkte, axis=1))))
    beste, beste_innen = standard, np.ones(len(punkte), bool)
    beste_n = 0
    for _ in range(150):
        i, j = rng.choice(len(punkte), 2, replace=False)
        r = punkte[j] - punkte[i]
        laenge = np.linalg.norm(r)
        if laenge < 1e-6:
            continue
        r = r / laenge
        abstand = np.linalg.norm(np.cross(punkte - punkte[i], r), axis=1)
        innen = abstand < toleranz
        if innen.sum() > beste_n:
            beste, beste_innen, beste_n = r, innen, int(innen.sum())
    # Richtung mit allen Punkten auf der Geraden nachschärfen
    auf = punkte[beste_innen]
    if len(auf) >= 2:
        _, _, vt = np.linalg.svd(auf - auf.mean(0), full_matrices=False)
        beste = _waagrecht(vt[0], oben)
        beste /= np.linalg.norm(beste)
    return beste, beste_innen


def _spanne(x: np.ndarray) -> float:
    """Ausdehnung ohne die äußersten Ausreißer."""
    return float(np.percentile(x, 99.5) - np.percentile(x, 0.5))


def _runden(x: float | None) -> int | None:
    return None if x is None or not np.isfinite(x) or x <= 0 else int(round(x / 10) * 10)


def bereich_messen(t: Tiefe, maske: np.ndarray, messungen: list[Messung], seed: int = 0) -> Masse:
    """Breite, Tiefe und Höhe (mm, auf 10 mm gerundet) des markierten Bereichs.

    Die Markierung gilt als Umriss des künftigen Möbels im Foto:
    - Reicht sie bis auf den Boden, ist ihre Unterkante die Vorderkante des Möbels am Boden. Daraus kommt die Breite,
      der Abstand bis zur Wand dahinter ist die Tiefe, und die Oberkante wird auf die Vorderseite projiziert (Höhe).
    - Sonst (z. B. ein Wandregal) liegt der Bereich auf der Wand: Breite und Höhe direkt dort, keine Tiefe.
    """
    faktoren, p = massstab(t, messungen)
    if not faktoren:
        return Masse(None, None, None, hinweise=["masse.keine_messung"])
    s = float(np.mean(faktoren))
    abweichung = (max(faktoren) - min(faktoren)) / s if len(faktoren) > 1 else None
    hinweise = ["masse.nachmessen"] if abweichung is not None and abweichung > ABWEICHUNG_WARNUNG else []

    markiert = _maske_anpassen(maske, t.karte.shape) & np.isfinite(t.karte) & (t.karte > 0)
    if t.flach:
        hinweise.append("masse.flach")
    if markiert.sum() < 20:
        return Masse(None, None, None, abweichung, hinweise + ["masse.zu_klein"])
    p = p * 1000 * s  # ab hier echte mm
    rng = np.random.default_rng(seed)
    oben, boden = _oben(p / (1000 * s), rng)
    boden = boden * 1000 * s if boden is not None else None
    punkte = p[markiert]
    hoehen = punkte @ oben

    # Unter- und Oberkante je Bildspalte
    spalten = np.flatnonzero(markiert.any(0))
    zeilen = np.arange(markiert.shape[0])[:, None]
    unten_y = np.where(markiert, zeilen, -1).max(0)[spalten]
    oben_y = np.where(markiert, zeilen, markiert.shape[0]).min(0)[spalten]
    # Nur flache Stücke der Unterkante: Wo sie steil ist, ist es eine senkrechte Kante des Umrisses, und der
    # Hintergrund dahinter liegt weiter hinten (würde die Breite zu groß machen).
    flach_unten = np.abs(np.gradient(unten_y.astype(float))) < 1.0 if len(spalten) > 1 else np.ones(1, bool)
    unterkante = p[unten_y, spalten][flach_unten] if flach_unten.any() else p[unten_y, spalten]
    oberkante = p[oben_y, spalten]

    toleranz = None if boden is None else max(40.0, 0.03 * float(np.median(unterkante[:, 2])))
    am_boden = boden is not None and float(np.median(np.abs(unterkante @ oben - boden))) < toleranz
    if boden is None and not t.flach:
        hinweise.append("masse.kein_boden")

    if am_boden:
        # Vorderkante: längste Gerade in der Unterkante (RANSAC), so stört eine sichtbare Seitenkante nicht
        vorne = _waagrecht(unterkante, oben)
        quer, auf_linie = _gerade(vorne, oben, rng)
        vorne = vorne[auf_linie]
        mitte = vorne.mean(0)
        weg = np.cross(oben, quer)  # waagrecht, quer zur Vorderkante
        if weg @ mitte < 0:
            weg = -weg  # von der Kamera weg zeigen lassen
        ebene = float(mitte @ weg)

        def auf_ebene(q: np.ndarray, abstand: float) -> np.ndarray:
            """Sichtstrahlen (von der Kamera durch q) bis zur senkrechten Ebene ``abstand`` hinter der Kamera."""
            r = q @ weg
            q = q[r > 1e-6]
            return q * (abstand / (r[r > 1e-6]))[:, None]

        # Breite: Umriss auf die Vorderseite projiziert (genauer als nur die Unterkante, deren Enden abgeschnitten sind)
        probe = punkte[:: max(1, len(punkte) // 20000)]
        breite = _spanne(auf_ebene(probe, ebene) @ quer) if len(probe) else _spanne(vorne @ quer)
        # Tiefe: wie weit der markierte Hintergrund (meist die Wand) hinter der Vorderkante liegt
        hinten = (_waagrecht(punkte, oben) - mitte) @ weg
        tiefe = float(np.percentile(hinten, 95))
        # Höhe: Sichtstrahl durch die Oberkante bis zur Vorderseite. Ist die Kamera höher als das Möbel, sieht sie
        # von oben drauf, die Oberkante im Bild ist dann die hintere Kante: also bis zur Rückseite rechnen.
        def hoehe_bei(abstand: float) -> float | None:
            q = auf_ebene(oberkante, abstand)
            return float(np.percentile(q @ oben - boden, 90)) if len(q) else None

        hoehe = hoehe_bei(ebene)
        kamera = -boden  # Kamera liegt im Ursprung, der Boden darunter
        if hoehe is not None and hoehe < kamera and MIN_TIEFE_MM <= tiefe <= MAX_TIEFE_MM:
            hoehe = hoehe_bei(ebene + tiefe)
        if hoehe is None:
            hoehe = float(np.percentile(hoehen, 98) - boden)
    else:
        flach_ = _waagrecht(punkte, oben)
        flach_ = flach_ - flach_.mean(0)
        _, _, vt = np.linalg.svd(flach_[:: max(1, len(flach_) // 20000)], full_matrices=False)
        breite = _spanne(flach_ @ vt[0])
        hoehe = _spanne(hoehen)
        tiefe = None
        if not t.flach:
            hinweise.append("masse.an_der_wand")

    if tiefe is None or tiefe < MIN_TIEFE_MM or tiefe > MAX_TIEFE_MM:
        tiefe = None
        if not t.flach:
            hinweise.append("masse.keine_tiefe")
    return Masse(_runden(breite), _runden(tiefe), _runden(hoehe),
                 round(abweichung, 3) if abweichung is not None else None, hinweise)
