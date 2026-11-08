"""Gegenprobe der Statik gegen eurocodepy (unabhängige Umsetzung von EN 1995-1-1, Eurocode 5).

Gleiche Kräfte, gleicher Querschnitt, gleiches Holz (C24, Nutzungsklasse 1, kurze Last): die Ausnutzung für Biegung,
Schub und Knicken muss übereinstimmen. eurocodepy läuft nur hier in den Tests, nicht auf dem Server.
"""
from __future__ import annotations

import pytest

from app.models.engine import statik as st
from app.models.engine.grundlagen import Bauteil

ec = pytest.importorskip("eurocodepy")
from eurocodepy.ec5.materials import LoadDuration, ServiceClass, Timber  # noqa: E402
from eurocodepy.ec5.uls.cross_section import TimberForces, TimberSectionInput, eurocode5_section_check  # noqa: E402
from eurocodepy.utils import RectangularCrossSection  # noqa: E402


def _ec5(b: float, h: float, forces: TimberForces, laenge: float = 0.0, ld=LoadDuration.ShortDuration):
    return eurocode5_section_check(TimberSectionInput(
        section=RectangularCrossSection(b / 1000, h / 1000), timber=Timber("C24"), service_class=ServiceClass.SC1,
        load_duration=ld, l_0y=laenge, l_0z=laenge), forces)


def test_holzwerte_wie_in_der_norm():
    t = Timber("C24")
    assert (t.fmk, t.fvk, t.fc0k, t.E0mean, t.E0k) == (st.F_M_K, st.F_V_K, st.F_C0_K, st.E_MEAN, st.E_005)
    assert t.safety == st.GAMMA_M
    assert t.k_mod(ServiceClass.SC1, LoadDuration.ShortDuration) == st.KMOD_KURZ
    assert t.k_mod(ServiceClass.SC1, LoadDuration.Permanent) == st.KMOD_DAUER
    assert t.kcr == st.K_CR


@pytest.mark.parametrize("b,h,L,P", [(44, 94, 1000, 1300), (34, 54, 500, 1300), (24, 44, 400, 650),
                                     (44, 94, 300, 2600), (44, 194, 1800, 1300), (18, 300, 800, 1300)])
def test_biegung_und_schub(b, h, L, P):
    m = Bauteil(min=[0, 0, 0], max=[L, b, h], long=0, rolle="zarge")
    w = st._balken(m, L, False, P=P).werte
    r = _ec5(b, h, TimberForces(my_ed=w["M"] / 1e6, vz_ed=w["V"] / 1e3))
    assert w["biegung"] == pytest.approx(r.util_bending_axial, rel=2e-3, abs=6e-4)
    assert w["schub"] == pytest.approx(r.util_shear, rel=2e-3, abs=6e-4)


@pytest.mark.parametrize("a,b,L,N", [(44, 44, 800, 3000), (44, 44, 450, 3000), (34, 54, 1200, 2000),
                                     (94, 94, 2000, 10000), (44, 74, 900, 4000)])
def test_knicken(a, b, L, N):
    m = Bauteil(min=[0, 0, 0], max=[a, b, L], long=2, rolle="bein")
    n = st._knicken(m, N)
    r = _ec5(max(a, b), min(a, b), TimberForces(n_ed=-N / 1e3), laenge=L)
    assert n.ausnutzung == pytest.approx(r.util_bending_axial, rel=1e-3)
    assert n.werte["kc"] == pytest.approx(min(r.k_c), abs=1e-3)
