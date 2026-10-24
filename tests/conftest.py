"""Jeder Test bekommt eine eigene, leere Verbrauchs-Datenbank."""
import pytest

from app.models import verbrauch


@pytest.fixture(autouse=True)
def eigene_datenbank(tmp_path, monkeypatch):
    monkeypatch.setattr(verbrauch, "STANDARD_URL", f"sqlite:///{tmp_path / 'verbrauch.db'}")
    verbrauch.datenbank.cache_clear()
    yield
    verbrauch.datenbank.cache_clear()
