import json
import os
import sys

from pathlib import Path

from .exceptions import InvalidConfigurationError
from .logging import LOGGER


DEFAULT_CONFIG_NAME = "pymanager.json"
ENV_VAR = "PYTHON_MANAGE_CONFIG"


def config_append(x, y):
    if isinstance(x, list):
        return [*x, y]
    return [x, y]


def config_bool(v):
    if not v:
        return False
    if isinstance(v, str):
        return v.lower().startswith(("t", "y", "1"))
    return True


def load_config(root, override_file, schema):
    cfg = {}
    env_file = os.getenv(ENV_VAR)
    if override_file:
        load_one_config(cfg, override_file, schema=schema)
    elif env_file:
        load_one_config(cfg, env_file, schema=schema)
    else:
        file = root / DEFAULT_CONFIG_NAME
        try:
            load_one_config(cfg, file, schema=schema)
        except FileNotFoundError:
            pass
    return cfg


def load_one_config(cfg, file, schema):
    with open(file, "r", encoding="utf-8") as f:
        cfg2 = json.load(f)
    cfg2["config_files"] = file
    resolve_config(cfg2, Path(file).absolute(), schema=schema)
    merge_config(cfg, cfg2, schema=schema)


def resolve_config(cfg, source_path, key_so_far="", schema=None):
    LOGGER.debug("resolve_config: %s", cfg)
    for k, v in list(cfg.items()):
        try:
            subschema = schema[k]
        except LookupError:
            raise InvalidConfigurationError(source_path, key_so_far + k)

        if isinstance(subschema, dict):
            if not isinstance(v, dict):
                raise InvalidConfigurationError(source_path, key_so_far + k, v)
            resolve_config(v, source_path, f"{key_so_far}{k}.", subschema)
            continue

        kind, merge, *opts = subschema
        if "env" in opts:
            try:
                v = os.path.expandvars(v)
            except TypeError:
                pass
        try:
            v = kind(v)
        except (TypeError, ValueError):
            raise InvalidConfigurationError(source_path, key_so_far + k, v)
        LOGGER.debug("Processing %s: %s", k, opts)
        if "path" in opts:
            v = Path(source_path).parent / v
        if "uri" in opts:
            if hasattr(v, 'as_uri'):
                v = v.as_uri()
            from urllib.parse import urlparse
            p = urlparse(v)
            if not p.scheme or not p.netloc or p.path.startswith(".."):
                raise InvalidConfigurationError(source_path, key_so_far + k, v)
        cfg[k] = v


def merge_config(into_cfg, from_cfg, schema):
    for k, v in from_cfg.items():
        try:
            into = into_cfg[k]
        except LookupError:
            into_cfg[k] = v
            continue

        try:
            subschema = schema[k]
        except LookupError:
            # No schema information, so let's just replace
            LOGGER.warn("Unknown configuration key %s", k)
            into_cfg[k] = v
            continue

        if isinstance(subschema, dict):
            if isinstance(into, dict) and isinstance(v, dict):
                LOGGER.debug("Recursively updating config %s", k)
                merge_config(into, v, subschema)
            else:
                # Source isn't recursing, so let's ignore
                # Should have been validated earlier
                LOGGER.warn("Invalid configuration key %s", k)
            continue

        _, merge, *_ = subschema
        if not merge:
            LOGGER.debug("Updating config %s from %r to %r", k, into, v)
            into_cfg[k] = v
        else:
            v2 = merge(into, v)
            LOGGER.debug("Updating config %s from %r to %r", k, into, v2)
            into_cfg[k] = v2
