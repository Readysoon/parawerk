"""Views: Jinja-Templates und statische Dateien der Oberfläche."""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from .praesentation import eur, meter

VIEWS = Path(__file__).parent
STATIC = VIEWS / "static"

templates = Jinja2Templates(directory=VIEWS / "templates")
templates.env.filters["eur"] = eur
templates.env.filters["meter"] = meter
