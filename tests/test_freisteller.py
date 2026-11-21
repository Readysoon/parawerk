"""Freistellen mit Bria auf fal: Datenschutz-Header, sync_mode, Alphakanal als Deckkraft."""
import asyncio
import base64
import io
import json

import httpx
from PIL import Image

from app.services.freisteller import FalBria


def _png_data_url(bild: Image.Image) -> str:
    puffer = io.BytesIO()
    bild.save(puffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(puffer.getvalue()).decode()


def test_bria_deckkraft_und_header():
    gesehen = {}

    def api(req: httpx.Request) -> httpx.Response:
        gesehen["url"], gesehen["kopf"], gesehen["daten"] = str(req.url), req.headers, json.loads(req.content)
        frei = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        frei.paste((200, 100, 50, 255), (0, 0, 20, 20))  # linke Hälfte ist das Möbel
        return httpx.Response(200, json={"image": {"url": _png_data_url(frei)}})

    maske = asyncio.run(FalBria("test", transport=httpx.MockTransport(api)).deckkraft(Image.new("RGB", (80, 40))))
    assert gesehen["url"] == "https://fal.run/fal-ai/bria/background/remove"
    assert gesehen["kopf"]["x-fal-store-io"] == "0"
    assert 0 < json.loads(gesehen["kopf"]["x-fal-object-lifecycle-preference"])["expiration_duration_seconds"] <= 3600
    assert gesehen["daten"]["sync_mode"] is True and gesehen["daten"]["image_url"].startswith("data:image/jpeg")
    assert maske.mode == "L" and maske.size == (80, 40)
    assert maske.getpixel((10, 20)) > 200 and maske.getpixel((70, 20)) < 50
