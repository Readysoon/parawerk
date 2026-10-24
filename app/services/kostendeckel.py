"""Kostendeckel: Wer darf wie oft einen KI-Dienst aufrufen, und wann ist für heute Schluss.

Vor jedem bezahlten Aufruf reserviert der Controller die geschätzten Kosten (``reservieren``); schlägt der
Aufruf fehl, gibt er sie zurück (``erstatten``). Gezählt wird nur, was wirklich Geld kostet, also nicht im
Demo-Modus.

Regeln (Werte in ``Einstellungen``):
- je Gerät insgesamt: ``gratis_runden`` Runden Entwürfe und ``gratis_nachjustieren`` Änderungen an Entwürfen
- je IP und Tag: ``ip_runden_pro_tag`` Runden (gegen neue Geräte-IDs durch gelöschte Cookies)
- je Gerät und Tag: ``lesen_pro_tag`` Lesungen und ``anpassen_pro_tag`` Anpassungen
- für alle zusammen: ``tagesbudget_usd`` als Notbremse, gilt auch mit Admin-Schlüssel
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from ..config import Einstellungen
from ..i18n import t
from ..models import verbrauch as v

# geschätzte Kosten je Aufruf in US-Dollar (Okt. 2026): FLUX Fill Pro 0,05 $/Bild, FLUX Kontext Pro 0,04 $/Bild,
# Claude Sonnet 5.5 2 $ / 10 $ je Million Tokens Ein-/Ausgabe
KOSTEN = {"runde": 0.21, "nachjustieren": 0.045, "lesen": 0.04, "anpassen": 0.04}


@dataclass(frozen=True)
class Kunde:
    geraet: str
    ip: str
    admin: bool = False


class Gesperrt(Exception):
    """Aufruf nicht erlaubt; ``status`` ist der HTTP-Status, ``args[0]`` die Meldung."""

    def __init__(self, status: int, meldung: str) -> None:
        super().__init__(meldung)
        self.status = status


class Kostendeckel:
    def __init__(self, db: Engine, e: Einstellungen) -> None:
        self.db, self.e = db, e

    def stand(self, k: Kunde) -> dict:
        """Was dieses Gerät noch gratis hat (für die Anzeige)."""
        if k.admin:
            return {"runden": None, "nachjustieren": None}
        return {
            "runden": max(0, self.e.gratis_runden - v.anzahl(self.db, "runde", geraet=k.geraet)),
            "nachjustieren": max(0, self.e.gratis_nachjustieren - v.anzahl(self.db, "nachjustieren", geraet=k.geraet)),
        }

    def _pruefen(self, art: str, k: Kunde) -> None:
        heute = v.heute_beginn()
        if v.kosten_seit(self.db, heute) + KOSTEN[art] > self.e.tagesbudget_usd:
            raise Gesperrt(503, t("fehler.budget"))
        if k.admin:
            return
        if art == "runde":
            if v.anzahl(self.db, "runde", geraet=k.geraet) >= self.e.gratis_runden:
                raise Gesperrt(402, t("fehler.gratis_runde"))
            if v.anzahl(self.db, "runde", ip=k.ip, seit=heute) >= self.e.ip_runden_pro_tag:
                raise Gesperrt(429, t("fehler.ip_limit"))
        elif art == "nachjustieren":
            if v.anzahl(self.db, "nachjustieren", geraet=k.geraet) >= self.e.gratis_nachjustieren:
                raise Gesperrt(402, t("fehler.gratis_nj", n=self.e.gratis_nachjustieren))
        elif art == "lesen":
            if v.anzahl(self.db, "lesen", geraet=k.geraet, seit=heute) >= self.e.lesen_pro_tag:
                raise Gesperrt(429, t("fehler.tageslimit"))
        elif art == "anpassen":
            if v.anzahl(self.db, "anpassen", geraet=k.geraet, seit=heute) >= self.e.anpassen_pro_tag:
                raise Gesperrt(429, t("fehler.tageslimit"))

    def reservieren(self, art: str, k: Kunde) -> int:
        """Prüft die Regeln und trägt die geschätzten Kosten ein. Gibt die Nummer des Eintrags zurück."""
        self._pruefen(art, k)
        return v.eintragen(self.db, k.geraet, k.ip, art, KOSTEN[art])

    def erstatten(self, eintrag: int | None) -> None:
        """Aufruf ist fehlgeschlagen: zählt weder fürs Kontingent noch fürs Budget."""
        if eintrag is not None:
            v.streichen(self.db, eintrag)
