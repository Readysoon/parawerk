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

    @property
    def bild_ki_aktiv(self) -> bool:
        return bool(self.replicate_api_token)

    @property
    def claude_aktiv(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()
