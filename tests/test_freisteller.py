"""fal.ai soll Eingaben und Ergebnisse nicht speichern (Datenschutz)."""
import json

from app.services.freisteller import FalBiRefNet


def test_fal_speichert_nichts():
    kopf = FalBiRefNet("test")._kopf
    assert kopf["X-Fal-Store-IO"] == "0"
    frist = json.loads(kopf["X-Fal-Object-Lifecycle-Preference"])["expiration_duration_seconds"]
    assert 0 < frist <= 3600
