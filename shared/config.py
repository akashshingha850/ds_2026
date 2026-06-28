# =============================================================================
# CONFIGURATION LOADER
# =============================================================================
# Reads the single config.yaml (repo root) and exposes every setting as a
# module-level constant, so existing `from config import NAME` imports keep
# working across all services. Any setting can be overridden at runtime by an
# environment variable of the same name (secrets stay in .env).
# =============================================================================
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_config():
    """Locate config.yaml.

    In the container both config.py and config.yaml are copied to /app (same
    dir). For local development config.py lives in shared/ while config.yaml
    sits at the repo root (parent dir). CONFIG_PATH overrides both.
    """
    for candidate in (
        os.getenv("CONFIG_PATH"),
        os.path.join(_HERE, "config.yaml"),          # container /app
        os.path.join(os.path.dirname(_HERE), "config.yaml"),  # repo root
    ):
        if candidate and os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("config.yaml not found (set CONFIG_PATH to override)")


_CONFIG_PATH = _find_config()


def _coerce(value, default):
    """Coerce an env-var string to the type of its YAML default."""
    if isinstance(default, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except ValueError:
            return default
    return value


def _load():
    with open(_CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f) or {}

    # Flatten the grouped sections into a single namespace of constants.
    flat = {}
    for value in raw.values():
        if isinstance(value, dict):
            flat.update(value)
    for key, value in raw.items():
        if not isinstance(value, dict):  # top-level scalars, if any
            flat[key] = value

    module = sys.modules[__name__]
    for key, default in flat.items():
        env = os.getenv(key)
        setattr(module, key, _coerce(env, default) if env is not None else default)


_load()
