#!/usr/bin/env python3
"""Load config.toml, applying environment-variable overrides.

Usage: python3 config.py --shell [config.toml]
  Prints the settings workflow_script.sh needs as shell assignments.
"""
import os
import shlex
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "config.toml")

# env var -> (section, key, type)
ENV_OVERRIDES = {
    "ADB_DEVICE": ("device", "adb_device", str),
    "WAYDROID_MODE": ("device", "waydroid", bool),
    "SCREEN_SIZE": ("device", "screen_size", str),
    "SCREEN_DENSITY": ("device", "screen_density", int),
    "KEEP_DISPLAY": ("device", "keep_display", bool),
    "LLM_ENABLED": ("llm", "enabled", bool),
    "LLM_URL": ("llm", "url", str),
    "LLM_MODEL": ("llm", "model", str),
    "LLM_API_KEY": ("llm", "api_key", str),
}


def _convert(value, typ):
    if typ is bool:
        return value.strip().lower() not in ("0", "false", "no", "")
    return typ(value)


def load(path=None):
    with open(path or DEFAULT_PATH, "rb") as f:
        cfg = tomllib.load(f)
    for section in ("device", "llm", "rules"):
        cfg.setdefault(section, {})
    for env, (section, key, typ) in ENV_OVERRIDES.items():
        if env in os.environ:
            cfg[section][key] = _convert(os.environ[env], typ)
    return cfg


def shell_lines(cfg):
    lines = []
    for env, (section, key, typ) in ENV_OVERRIDES.items():
        if env == "LLM_API_KEY":
            continue  # the shell script doesn't need the key
        v = cfg[section].get(key, "")
        if typ is bool:
            v = "1" if v else "0"
        lines.append(f"{env}={shlex.quote(str(v))}")
    return lines


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "--shell":
        print(__doc__)
        sys.exit(1)
    print("\n".join(shell_lines(load(sys.argv[2] if len(sys.argv) > 2 else None))))
