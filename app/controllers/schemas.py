"""Anfragen und Antworten der API (Validierung an der Grenze zum Browser)."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Mass = Annotated[float, Field(gt=0, le=20000)]
Bereich = Annotated[list[Mass], Field(min_length=3, max_length=3, description="Breite × Tiefe × Höhe in mm")]
DataUrl = Annotated[str, Field(max_length=16_000_000, pattern=r"^data:image/")]


class EntwuerfeAnfrage(BaseModel):
    foto: DataUrl | None = None
    maske: DataUrl | None = None
    wunsch: str = Field("", max_length=500)


class EntwuerfeAntwort(BaseModel):
    demo: bool
    prompt: str
    bilder: list[str]


class NachjustierenAnfrage(BaseModel):
    bild: DataUrl
    wunsch: str = Field("", max_length=500)
    anpassung: str = Field(min_length=1, max_length=500)


class NachjustierenAntwort(BaseModel):
    prompt: str
    bild: str


class LesenAnfrage(BaseModel):
    bild: DataUrl | None = None
    bereich: Bereich = [2000, 1000, 1000]
    demo_index: int | None = None


class AnpassenAnfrage(BaseModel):
    graph: dict
    wunsch: str = Field(min_length=1, max_length=500)


class GraphAntwort(BaseModel):
    demo: bool = False
    graph: dict


class BerechnenAnfrage(BaseModel):
    graph: dict
    bereich: Bereich
    sortiment: Literal["DE", "US"] | None = None


class Fehler(BaseModel):
    fehler: str
