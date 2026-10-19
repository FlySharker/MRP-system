"""Backend configuration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent
DATA_PATH = None

DEFAULT_CONFIG = {
    "window_size": 5,
    "time_window_size": "14D",
    "quantile": 0.75,
    "min_interval_len": 3,
    "max_materials": 5,
}
