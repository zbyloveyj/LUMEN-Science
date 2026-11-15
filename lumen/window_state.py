"""Best-effort desktop geometry persistence; settings must never prevent launch."""
from __future__ import annotations

import json


def load_window_state(root, screens):
    default = {"width": 1440, "height": 960}
    try:
        value = json.loads((root / "window.json").read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return default
        bounds = {key: value[key] for key in ("width", "height", "x", "y")}
        if any(type(v) is not int for v in bounds.values()):
            return default
        if not (1000 <= bounds["width"] <= 10000 and 700 <= bounds["height"] <= 10000):
            return default
        # Restore only if the full title bar remains reachable on an attached display.
        for screen in screens:
            if (screen.x <= bounds["x"] <= screen.x + screen.width - 100
                    and screen.y <= bounds["y"] <= screen.y + screen.height - 50):
                bounds["width"] = max(1000, min(bounds["width"], screen.width))
                bounds["height"] = max(700, min(bounds["height"], screen.height))
                return bounds
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return default


def save_window_state(root, window):
    try:
        value = {key: int(getattr(window, key)) for key in ("width", "height", "x", "y")}
        pending = root / "window.json.tmp"
        pending.write_text(json.dumps(value), encoding="utf-8")
        pending.replace(root / "window.json")
    except (OSError, ValueError, TypeError, AttributeError):
        pass
