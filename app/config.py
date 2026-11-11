"""Einstellungen aus Umgebungsvariablen bzw. ``.env``."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Einstellungen(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Bildgenerierung (Entwürfe) über Replicate, FLUX Fill Pro
    replicate_api_token: str = ""
    replicate_model: str = "black-forest-labs/flux-fill-pro"
    # Nachjustieren eines Entwurfs per Text. Getestet: FLUX Kontext; die Eingaben für andere Modelle (Nano Banana,
    # FLUX 2, Seedream, Qwen) stehen in bild_ki.bearbeitungs_eingabe – zum Vergleichen scripts/anpassen_vergleich.py
    replicate_edit_model: str = "black-forest-labs/flux-kontext-pro"
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
    nj_kontrolle: bool = True
    # Fotos und Bilder verschlüsselt speichern (32 Byte, base64; siehe app/models/tresor.py). Leer = unverschlüsselt
    daten_schluessel: str = ""  # Nachjustieren: Claude prüft, ob die Änderung zu sehen ist; sonst ein zweiter Versuch
    tagesbudget_usd: float = 5.0  # alle zusammen, Notbremse
    # Testcodes: "KUMPEL:10,FREUNDE:5:3,PARTNER:0:20:3" = Code:Runden[:Geräte[:Baupläne]]; ohne Geräte-Angabe ein Gerät.
    # Baupläne = wie viele Baupläne der Code je Gerät bzw. Konto freischaltet (nur wichtig mit BEZAHLUNG_PFLICHT)
    testcodes: str = ""
    admin_schluessel: str = ""
    oeffentliche_url: str = "https://parawerk.fly.dev"  # für Links und QR-Codes in der PDF
    # Stufen (siehe projekt-docs/entscheidungen): 1. Foto + eine Runde Entwürfe ohne Konto; 2. Anpassen, weitere
    # Runden und Umwandeln in einen Bauplan nur mit Gratis-Konto; 3. vollständiger Bauplan (Einkauf, Zuschnitt,
    # Schritte, PDF) nur freigeschaltet. Aus = wie bisher (für die TestFlight-Version ohne Anmeldung).
    konto_pflicht: bool = False
    bezahlung_pflicht: bool = False
    gratis_runden_konto: int = 3  # Runden insgesamt je Konto (statt gratis_runden je Gerät)
    # Stufen lokal durchspielen, z. B. mit der Flutter-App im Browser (nie auf fly.io setzen):
    # - „Demo-Anmeldung“ ohne Apple/Google, auch mit KI-Schlüsseln, aber nur direkt vom selben Computer
    # - im Demo-Modus (ohne KI-Schlüssel) zählen Runden und Lesen trotzdem, kostenlos
    stufen_simulieren: bool = False
    # Anmelden mit Apple und Google: erlaubte Client-IDs, durch Komma getrennt.
    # Apple: Bundle-ID der App (at.parawerk.parawerk) und, für die Website, die Services-ID.
    # Google: OAuth-Client-IDs für iOS, Android und Web aus der Google Cloud Console.
    apple_client_ids: str = "at.parawerk.parawerk"
    apple_web_client_id: str = ""  # Services-ID für „Mit Apple anmelden“ auf der Website (leer: Knopf ausgeblendet)
    google_client_ids: str = ""
    google_web_client_id: str = ""  # Web-Client-ID für den Google-Knopf auf der Website (leer: Knopf ausgeblendet)

    def client_ids(self, anbieter: str) -> list[str]:
        roh = {"apple": self.apple_client_ids + "," + self.apple_web_client_id,
               "google": self.google_client_ids + "," + self.google_web_client_id}.get(anbieter, "")
        return [x.strip() for x in roh.split(",") if x.strip()]  # ?schluessel=… auf der Startseite hebt die Kontingente für diesen Browser auf

    @property
    def codes(self) -> dict[str, tuple[int, int]]:
        """Testcodes als {CODE: (Runden, Geräte)}; Groß-/Kleinschreibung egal, kaputte Einträge werden übersprungen."""
        out: dict[str, tuple[int, int]] = {}
        for eintrag in self.testcodes.split(","):
            teile = [x.strip() for x in eintrag.split(":")]
            if len(teile) in (2, 3, 4) and teile[0] and all(x.isdigit() for x in teile[1:]):
                out[teile[0].upper()] = (int(teile[1]), int(teile[2]) if len(teile) == 3 else 1)
        return out

    @property
    def code_plaene(self) -> dict[str, int]:
        """Wie viele Baupläne ein Code freischaltet (4. Feld), {CODE: Anzahl}."""
        out: dict[str, int] = {}
        for eintrag in self.testcodes.split(","):
            teile = [x.strip() for x in eintrag.split(":")]
            if len(teile) == 4 and teile[0] and all(x.isdigit() for x in teile[1:]):
                out[teile[0].upper()] = int(teile[3])
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
