from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
EXPORT_DIR = BASE_DIR / "json_exports"

def export_json(*parts) -> Path:
    return EXPORT_DIR.joinpath(*parts)
