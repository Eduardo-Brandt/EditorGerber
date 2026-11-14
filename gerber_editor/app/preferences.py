"""Versioned, atomic preferences; never written inside a Gerber file."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from gerber_editor.app.i18n import Locale

DEFAULTS = {
    "schema": 1,
    "language": "pt_BR",
    "units": "mm",
    "grid_mm": "0.635",
    "grids_mm": ["0.0254", "0.05", "0.1", "0.254", "0.5", "0.635", "1", "2.54"],
    "shortcuts": {},
    "full_cursor": False,
    "polar": False,
    "ghost_negatives": False,
    "grid_visible": False,
    "snap_grid": True,
    "snap_points": True,
    "ortho_angle": 45,
    "background": "#000000",
    "text_defaults": {},
    "expanded_tools": True,
    "last_directory": "",
    "last_export_directory": "",
}


class Preferences:
    def __init__(self, path: Path | None = None):
        override = os.environ.get("EDITOR_GERBER_SETTINGS") or os.environ.get(
            "EDITR_GERBER_SETTINGS"
        )
        default_location = path is None and not override
        if path is None:
            path = (
                Path(override)
                if override
                else Path(
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.AppConfigLocation
                    )
                )
                / "preferences.json"
            )
        self.path = Path(path)
        self.data = deepcopy(DEFAULTS)
        self.warning = ""
        read_path = self.path
        if (
            default_location
            and not read_path.is_file()
            and read_path.parent.name == "Editor Gerber"
        ):
            # Retain settings saved before correcting the application name.
            read_path = read_path.parent.with_name("Editr Gerber") / read_path.name
        if read_path.is_file():
            try:
                loaded = json.loads(read_path.read_text(encoding="utf-8"))
                self._validate(loaded)
                self.data.update(loaded)
                if self.data["shortcuts"].get("edit.copy") == "Ctrl+D":
                    self.data["shortcuts"] = {**self.data["shortcuts"], "edit.copy": "Ctrl+C"}
                    self.data["shortcuts"].setdefault("edit.duplicate", "Ctrl+D")
            except (OSError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
                self.warning = str(exc)

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict) or data.get("schema", 1) != 1:
            raise ValueError("Unsupported preferences schema")
        if data.get("language", "pt_BR") not in Locale.languages:
            raise ValueError("Unsupported language")
        if data.get("units", "mm") not in ("mm", "in", "mil"):
            raise ValueError("Invalid display unit")
        text = data.get("text_defaults", {})
        if not isinstance(text, dict):
            raise ValueError("Invalid text defaults")
        if text:
            from gerber_editor.core.primitives import Point
            from gerber_editor.core.text_entity import TextEntity

            entity = TextEntity(
                **{
                    **text,
                    "height": Decimal(text["height"]),
                    "stroke": Decimal(text["stroke"]),
                    "position": Point.of(0, 0),
                }
            )
            if (
                not entity.height.is_finite()
                or entity.height <= 0
                or not entity.stroke.is_finite()
                or entity.stroke <= 0
            ):
                raise ValueError("Invalid text dimensions")
        grids = data.get("grids_mm", DEFAULTS["grids_mm"])
        if not isinstance(grids, list) or not 1 <= len(grids) <= 100:
            raise ValueError("Invalid grid list")
        for value in [data.get("grid_mm", "0.635"), *grids]:
            value = Decimal(str(value))
            if not value.is_finite() or not Decimal("0.000001") <= value <= 100000:
                raise ValueError("Invalid grid spacing")
        if not isinstance(data.get("shortcuts", {}), dict):
            raise ValueError("Invalid shortcuts")
        if any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in data.get("shortcuts", {}).items()
        ):
            raise ValueError("Invalid shortcut values")
        if data.get("ortho_angle", 45) not in (45, 90):
            raise ValueError("Invalid ortho angle")
        for key in (
            "full_cursor",
            "polar",
            "ghost_negatives",
            "grid_visible",
            "snap_grid",
            "snap_points",
            "expanded_tools",
        ):
            if key in data and not isinstance(data[key], bool):
                raise ValueError(f"Invalid {key}")
        for key in ("last_directory", "last_export_directory"):
            if key in data and not isinstance(data[key], str):
                raise ValueError(f"Invalid {key}")

    def set(self, **values):
        data = {**self.data, **values}
        self._validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".preferences-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.data = data
