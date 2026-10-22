"""Welche Dienste die Controller bekommen. Ohne API-Schlüssel laufen die Demo-Dienste.

In Tests lassen sie sich über ``app.dependency_overrides`` ersetzen.
"""
from __future__ import annotations

from fastapi import Depends

from ..config import Einstellungen, einstellungen
from ..services.bild_ki import BildKI, DemoBildKI, ReplicateFluxFill
from ..services.konstrukteur import ClaudeKonstrukteur, DemoKonstrukteur, Konstrukteur


def bild_ki(e: Einstellungen = Depends(einstellungen)) -> BildKI:
    return ReplicateFluxFill(e.replicate_api_token, e.replicate_model) if e.bild_ki_aktiv else DemoBildKI()


def konstrukteur(e: Einstellungen = Depends(einstellungen)) -> Konstrukteur:
    return ClaudeKonstrukteur(e.anthropic_api_key, e.anthropic_model) if e.claude_aktiv else DemoKonstrukteur()
