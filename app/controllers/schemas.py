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


class FotoV1(BaseModel):
    foto: DataUrl


Relativ = Annotated[float, Field(ge=0, le=1)]


class MessungV1(BaseModel):
    """Eine Strecke im Foto: zwei Punkte relativ zur Bildgröße (0–1, links oben = 0,0) und ihre echte Länge."""
    a: Annotated[list[Relativ], Field(min_length=2, max_length=2)]
    b: Annotated[list[Relativ], Field(min_length=2, max_length=2)]
    mm: Mass


class MasseV1(BaseModel):
    tiefe_id: BildId = Field(max_length=32, description="aus dem Ergebnis von POST /fotos")
    maske: DataUrl | None = None
    maske_id: BildId | None = Field(None, max_length=32)
    messungen: list[MessungV1] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def _maske(self):
        if not (self.maske or self.maske_id):
            raise ValueError("maske/maske_id")
        return self


class MasseAntwort(BaseModel):
    bereich: list[int | None] = Field(description="Breite × Tiefe × Höhe in mm; null = nicht messbar, selbst eintragen")
    abweichung: float | None = Field(None, description="bei 2+ Messungen: Unterschied der Maßstäbe (0.05 = 5 %)")
    nachmessen: bool = False
    hinweise: list[str] = Field(default_factory=list, description="in der Sprache der Anfrage")


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


class CodeAnfrage(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class AnpassenAnfrage(BaseModel):
    graph: dict
    wunsch: str = Field(min_length=1, max_length=500)


class Fehler(BaseModel):
    fehler: str
