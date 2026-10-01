"""Vị trí file của plugin trong thư mục profile Hermes."""

from __future__ import annotations

from pathlib import Path

from hermes_constants import get_hermes_home

PLATFORM = "zalo_ca_nhan"
PLUGIN_DIR = Path(__file__).parent
BRIDGE_SCRIPT = PLUGIN_DIR / "node" / "bridge.mjs"


def data_dir() -> Path:
    return get_hermes_home() / PLATFORM


def session_file() -> Path:
    return data_dir() / "session.json"


def qr_file() -> Path:
    return data_dir() / "qr-dang-nhap.png"


def state_file() -> Path:
    return data_dir() / "state.sqlite3"


def deps_installed() -> bool:
    return (PLUGIN_DIR / "node_modules" / "zca-js" / "package.json").exists()
