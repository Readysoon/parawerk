"""Anfragen und Antworten der API v1 (Validierung an der Grenze zu Browser und App)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

Mass = Annotated[float, Field(gt=0, le=20000)]
Bereich = Annotated[list[Mass], Field(min_length=3, max_length=3, description="Breite × Tiefe × Höhe in mm")]
DataUrl = Annotated[str, Field(max_length=16_000_000, pattern=r"^data:image/")]


BildId = str  # 32 Hex-Zeichen, vom Server vergeben


class EntwuerfeV1(BaseModel):
    """Foto und Maske als data-URL (erste Runde) oder als IDs aus einer früheren Antwort (neue Entwürfe)."""
    foto: DataUrl | None = None
    maske: DataUrl | None = Field(None, description="PNG in Fotogröße, weiß (oder deckend) = hier soll das Möbel hin")
    foto_id: BildId | None = Field(None, max_length=32)
    maske_id: BildId | None = Field(None, max_length=32)
    wunsch: str = Field("", max_length=500)

    @model_validator(mode="after")
    def _beides(self):
        if not (self.foto or self.foto_id) or not (self.maske or self.maske_id):
            raise ValueError("foto/foto_id und maske/maske_id")
        return self


class NachjustierenV1(BaseModel):
    foto_id: BildId = Field(max_length=32)
    maske_id: BildId = Field(max_length=32)
    entwurf_id: BildId = Field(max_length=32)
    wunsch: str = Field("", max_length=500)
    anpassung: str = Field(min_length=1, max_length=500)


class LesenV1(BaseModel):
    entwurf_id: BildId = Field(max_length=32)
    maske_id: BildId = Field(max_length=32)
    bereich: Bereich
    demo_index: int | None = Field(None, description="Nur im Demo-Modus: Nummer des Beispielentwurfs (0–3)")


class BerechnenV1(BaseModel):
    graph: dict
    bereich: Bereich
    sortiment: Literal["DE", "US"] | None = None


class AuftragAntwort(BaseModel):
    auftrag: str
    foto_id: str | None = None
    maske_id: str | None = None


class AuftragStand(BaseModel):
    id: str
    art: str
    status: Literal["laeuft", "fertig", "fehler"]
    ergebnis: dict[str, Any] | None = None
    fehler: str | None = None


class BauplanAntwort(BaseModel):
    name: str
    offene_punkte: int
    bauplan: dict[str, Any] = Field(description="Prüfungen, Rechenweg, Einkauf, Zuschnitt, Montage, in der Sprache der Anfrage")
    modell: dict[str, Any] = Field(description="Teile als Quader in mm, für eigene 3D-Anzeige")
    modell_glb: str | None = Field(None, description="URL des 3D-Modells als glTF-Binärdatei")
    plan: dict[str, Any] = Field(description="Rohdaten des Bauplans")
    html: str | None = Field(None, description="Nur mit mit_html=true: fertiger Bauplan-Ausschnitt für die Website")


class AnpassenAnfrage(BaseModel):
    graph: dict
    wunsch: str = Field(min_length=1, max_length=500)


class Fehler(BaseModel):
    fehler: str
