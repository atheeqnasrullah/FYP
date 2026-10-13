from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]

def load_settings():
    with (ROOT / "config/settings.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)
