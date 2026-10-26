"""Einstellungen aus Umgebungsvariablen bzw. ``.env``."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Einstellungen(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Bildgenerierung (Entwürfe) über Replicate, FLUX Fill Pro
    replicate_api_token: str = ""
    replicate_model: str = "black-forest-labs/flux-fill-pro"
    replicate_edit_model: str = "black-forest-labs/flux-kontext-pro"  # Nachjustieren eines Entwurfs per Text
    # Tiefe aus dem Foto (für Raummaße): Apple Depth Pro; kein offizielles Modell, darum mit Version
    replicate_tiefe_model: str = "ibrahimpenekli/depth-pro:8bee17f621ab23567c836703be980b3aa1552127b252b7ef9f6ce6db6c4619ef"
    # Konstruktion lesen und anpassen über die Claude-API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    # Holz-Sortiment: DE (Baumarkt) oder US (Bauholz)
    sortiment: str = "DE"
    anzahl_entwuerfe: int = 4
    # Kostendeckel (siehe services/kostendeckel.py); Datenbank: leer = SQLite im Temp-Ordner, auf fly.io Postgres
    database_url: str = ""
    gratis_runden: int = 1  # je Gerät insgesamt, eine Runde = 4 Entwürfe
    gratis_nachjustieren: int = 2  # je Gerät insgesamt
    ip_runden_pro_tag: int = 3
    lesen_pro_tag: int = 5  # je Gerät
    anpassen_pro_tag: int = 10  # je Gerät
    fotos_pro_tag: int = 20  # je Gerät: Tiefe schätzen (sehr billig, nur gegen Missbrauch)
    selbstkontrolle: bool = True  # Claude vergleicht das berechnete Modell mit dem Entwurf und korrigiert
    kontrollrunden: int = 2  # weitere Runden nur, solange die Endkontrolle der Engine noch etwas meldet
    tagesbudget_usd: float = 5.0  # alle zusammen, Notbremse
    # Testcodes für Tester: "KUMPEL:10,FREUNDE:5:3" = Code:Runden[:Geräte]; ohne Geräte-Angabe genau ein Gerät
    testcodes: str = ""
    admin_schluessel: str = ""  # ?schluessel=… auf der Startseite hebt die Kontingente für diesen Browser auf

    @property
    def codes(self) -> dict[str, tuple[int, int]]:
        """Testcodes als {CODE: (Runden, Geräte)}; Groß-/Kleinschreibung egal, kaputte Einträge werden übersprungen."""
        out: dict[str, tuple[int, int]] = {}
        for eintrag in self.testcodes.split(","):
            teile = [x.strip() for x in eintrag.split(":")]
            if len(teile) in (2, 3) and teile[0] and all(x.isdigit() for x in teile[1:]):
                out[teile[0].upper()] = (int(teile[1]), int(teile[2]) if len(teile) == 3 else 1)
        return out

    @property
    def bild_ki_aktiv(self) -> bool:
        return bool(self.replicate_api_token)

    @property
    def claude_aktiv(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()
