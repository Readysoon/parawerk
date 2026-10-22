import sys

if sys.version_info < (3, 11):
    raise RuntimeError(
        f"Parawerk braucht Python 3.11 oder neuer, gestartet wurde {sys.version.split()[0]}. "
        "Auf dem Mac z. B.: brew install python@3.12, dann das venv mit python3.12 neu anlegen (siehe README)."
    )
