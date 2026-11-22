from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def clean_scalar(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value):
        return None
    return value


def relative_posix_path(path: Path, root: Path) -> str:
    """Return path relative to root formatted as a normalized POSIX string."""
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root:
        return "."
    return resolved_path.relative_to(resolved_root).as_posix()


def is_relative_posix_path(value: object) -> bool:
    """Validate that value is a non-empty normalized relative POSIX path."""
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or value.startswith("/"):
        return False
    if len(value) >= 2 and value[1] == ":":
        return False
    if Path(value).is_absolute():
        return False
    return ".." not in Path(value).parts


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): clean_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8", lineterminator="\n")
    os.replace(temporary, path)


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_bytes(source.read_bytes())
    if sha256_file(source) != sha256_file(temporary):
        temporary.unlink(missing_ok=True)
        raise IOError(f"Hash mismatch while copying: {destination}")
    os.replace(temporary, destination)


def stable_hash_rows(paths: Iterable[Path], *, root: Path) -> pd.DataFrame:
    rows = [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths)
    ]
    return pd.DataFrame(rows)
