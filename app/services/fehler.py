"""Fehler der externen Dienste."""


class DienstFehler(RuntimeError):
    """Ein externer Dienst hat nicht wie erwartet geantwortet."""


class NichtVerfuegbar(DienstFehler):
    """Die Funktion braucht einen API-Schlüssel, der nicht hinterlegt ist."""
