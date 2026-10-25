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
    selbstkontrolle: bool = True  # Claude vergleicht das berechnete Modell mit dem Entwurf und korrigiert
    kontrollrunden: int = 2  # weitere Runden nur, solange die Endkontrolle der Engine noch etwas meldet
    tagesbudget_usd: float = 5.0  # alle zusammen, Notbremse
    admin_schluessel: str = ""  # ?schluessel=… auf der Startseite hebt die Kontingente für diesen Browser auf

    @property
    def bild_ki_aktiv(self) -> bool:
        return bool(self.replicate_api_token)

    @property
    def claude_aktiv(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()
