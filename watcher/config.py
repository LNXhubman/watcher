"""Load and validate config.toml."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class Config:
    zipcode: str
    bulk_model: str
    report_model: str
    daily_cap_usd: float
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "watcher.db"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"


def load(path: str | Path = DEFAULT_PATH) -> Config:
    path = Path(path)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    try:
        zipcode = str(raw["watch"]["zipcode"])
        bulk_model = raw["llm"]["bulk_model"]
        report_model = raw["llm"]["report_model"]
        cap = float(raw["budget"]["daily_cap_usd"])
    except KeyError as e:
        raise ValueError(f"{path}: missing config key {e}") from e
    if not re.fullmatch(r"\d{5}", zipcode):
        raise ValueError(f"{path}: watch.zipcode must be 5 digits, got {zipcode!r}")
    if cap <= 0:
        raise ValueError(f"{path}: budget.daily_cap_usd must be positive")
    data_dir = path.parent / raw.get("storage", {}).get("data_dir", "data")
    return Config(zipcode, bulk_model, report_model, cap, data_dir)
