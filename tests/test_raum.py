"""Raummaße aus Tiefenkarte und Messung, geprüft an einem gerechneten Zimmer mit bekannten Maßen."""
from __future__ import annotations

import numpy as np
import pytest

from app.models.raum import Messung, Tiefe, bereich_messen, flach

W, H = 400, 300
F = 330.0  # Brennweite in Pixeln (etwa Handy-Weitwinkel)


def _drehung(neigung_grad: float, drehung_grad: float) -> np.ndarray:
    """Kamera → Welt: erst nach unten neigen (um x), dann seitlich drehen (um y). Welt: y nach unten, Boden y = +hoehe."""
    a, b = np.radians(neigung_grad), np.radians(drehung_grad)
    rx = np.array([[1, 0, 0], [0, np.cos(a), np.sin(a)], [0, -np.sin(a), np.cos(a)]])
    ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    return ry @ rx


def zimmer(neigung=15.0, drehung=0.0, kamera_hoehe=1.4, wand=3.5, moebel=(1.8, 0.8, 0.9), moebel_x=0.0, skala=1.0):
    """Leeres Zimmer (Boden, Rückwand, Seitenwände) als Tiefenkarte; Maske = Umriss eines Quaders an der Rückwand.

    ``skala`` verfälscht die Tiefe wie ein Tiefenmodell, das den Maßstab falsch schätzt.
    Gibt Tiefe, Maske und eine Funktion zurück, die Weltpunkte auf relative Bildpunkte abbildet.
    """
    rot = _drehung(neigung, drehung)
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    d_kam = np.stack([(u - W / 2) / F, (v - H / 2) / F, np.ones_like(u)], -1)
    d = d_kam @ rot.T

    def treffer(achse, wert):
        with np.errstate(divide="ignore", invalid="ignore"):
            t = wert / d[..., achse]
        return np.where(t > 0, t, np.inf)

    t = np.minimum.reduce([treffer(1, kamera_hoehe), treffer(2, wand), treffer(0, 2.5), treffer(0, -2.5),
                           treffer(1, -1.2)])
    tiefe = t  # weil d_kam.z = 1, ist t direkt die Tiefe entlang der Blickrichtung

    # Quader: Breite × Tiefe × Höhe, steht am Boden an der Rückwand
    b, tq, hq = moebel
    lo = np.array([moebel_x - b / 2, kamera_hoehe - hq, wand - tq])
    hi = np.array([moebel_x + b / 2, kamera_hoehe, wand])
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (lo - 0) / d, (hi - 0) / d
    tmin = np.minimum(t1, t2).max(-1)
    tmax = np.maximum(t1, t2).min(-1)
    maske = (tmax >= tmin) & (tmax > 0)

    def bildpunkt(welt):
        k = np.asarray(welt) @ rot  # Welt → Kamera
        return ((k[0] / k[2] * F + W / 2) / W, (k[1] / k[2] * F + H / 2) / H)

    return Tiefe(tiefe.astype(np.float32) * skala, F), maske, bildpunkt


def _messung_rueckwand(bildpunkt, kamera_hoehe=1.4, wand=3.5, x=-1.0):
    """Echte Strecke an der Rückwand: 2 m waagrecht in 1,2 m Höhe über dem Boden, ab ``x``."""
    y = kamera_hoehe - 1.2
    m = Messung(bildpunkt([x, y, wand]), bildpunkt([x + 2.0, y, wand]), 2000)
    assert all(0 <= v <= 1 for v in (*m.a, *m.b)), "Messpunkt außerhalb des Bildes"
    return m


@pytest.mark.parametrize("skala", [1.0, 0.8, 1.3])
def test_bank_an_der_wand(skala):
    t, maske, bp = zimmer(skala=skala)
    m = bereich_messen(t, maske, [_messung_rueckwand(bp)])
    assert m.breite == pytest.approx(1800, rel=0.04)
    assert m.tiefe == pytest.approx(800, rel=0.08)
    assert m.hoehe == pytest.approx(900, rel=0.04)
    assert "masse.kein_boden" not in m.hinweise


def test_schraeg_fotografiert():
    t, maske, bp = zimmer(drehung=20, moebel_x=0.6, neigung=10)
    m = bereich_messen(t, maske, [_messung_rueckwand(bp, x=0.0)])
    assert m.breite == pytest.approx(1800, rel=0.06)
    assert m.tiefe == pytest.approx(800, rel=0.15)


def test_zwei_messungen_passen_und_passen_nicht():
    t, maske, bp = zimmer()
    gut = [_messung_rueckwand(bp), Messung(bp([-1.5, 1.4, 3.5]), bp([-1.5, 1.4 - 1.0, 3.5]), 1000)]  # senkrecht ab Boden
    m = bereich_messen(t, maske, gut)
    assert m.abweichung < 0.03 and "masse.nachmessen" not in m.hinweise
    falsch = [_messung_rueckwand(bp), Messung(gut[1].a, gut[1].b, 1400)]
    assert "masse.nachmessen" in bereich_messen(t, maske, falsch).hinweise


def test_wandregal_ohne_boden():
    t, _, bp = zimmer()
    maske = np.zeros((H, W), bool)
    links, rechts = bp([-0.6, 1.4 - 1.8, 3.5]), bp([0.6, 1.4 - 1.4, 3.5])
    maske[int(links[1] * H):int(rechts[1] * H), int(links[0] * W):int(rechts[0] * W)] = True
    m = bereich_messen(t, maske, [_messung_rueckwand(bp)])
    assert m.breite == pytest.approx(1200, rel=0.05)
    assert m.hoehe == pytest.approx(400, rel=0.1)
    assert m.tiefe is None and "masse.an_der_wand" in m.hinweise


def test_ohne_messung_und_leere_maske():
    t, maske, bp = zimmer()
    assert bereich_messen(t, maske, []).breite is None
    assert "masse.zu_klein" in bereich_messen(t, np.zeros_like(maske), [_messung_rueckwand(bp)]).hinweise


def test_flach_skaliert_wie_ein_lineal():
    t = flach(800, 600)
    maske = np.zeros((600, 800), np.uint8)
    maske[200:400, 100:500] = 255  # 400 px breit, 200 px hoch
    m = bereich_messen(t, maske, [Messung((0.0, 0.5), (0.5, 0.5), 1000)])  # 400 px = 1000 mm
    assert m.breite == pytest.approx(1000, rel=0.03) and m.hoehe == pytest.approx(500, rel=0.03)


def test_speichern_und_laden():
    t, _, _ = zimmer()
    t2 = Tiefe.aus_bytes(t.verkleinert().als_bytes())
    assert t2.karte.shape == t.karte.shape and t2.brennweite == pytest.approx(F)
    assert np.allclose(t2.karte, t.karte, rtol=1e-3)


def test_ungenaues_tiefenmodell():
    """Wie ein echtes Tiefenmodell: 2 % Rauschen je Pixel und 8 % Verzerrung von oben nach unten."""
    t, maske, bp = zimmer()
    rng = np.random.default_rng(1)
    karte = t.karte * np.linspace(0.96, 1.04, H)[:, None] * (1 + 0.02 * rng.standard_normal(t.karte.shape))
    m = bereich_messen(Tiefe(karte.astype(np.float32), F), maske, [_messung_rueckwand(bp)])
    assert m.breite == pytest.approx(1800, rel=0.05)
    assert m.tiefe == pytest.approx(800, rel=0.15)
    assert m.hoehe == pytest.approx(900, rel=0.06)
