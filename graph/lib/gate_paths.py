"""Read the paths a campaign declares for its gates."""

import json
import pathlib


def options(workspace) -> dict:
    path = pathlib.Path(workspace) / "gate-paths.json"
    if not path.exists():
        return {}
    declared = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict) or set(declared) - {"read_only", "cache"}:
        raise ValueError("gate paths must declare only read_only and cache")
    read_only = declared.get("read_only", [])
    cache = declared.get("cache")
    if not isinstance(read_only, list):
        raise TypeError("read_only must be a list of absolute paths")
    for value in read_only + ([] if cache is None else [cache]):
        if not isinstance(value, str) or not pathlib.Path(value).is_absolute():
            raise ValueError("gate paths must be absolute")
    return {"paths": declared} if read_only or cache else {}
