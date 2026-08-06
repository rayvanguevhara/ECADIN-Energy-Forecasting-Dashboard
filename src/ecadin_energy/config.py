from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    data: Path
    outputs: Path
    frontend: Path

    @classmethod
    def from_root(cls, root: Path) -> "ProjectPaths":
        root = root.resolve()
        return cls(
            root=root,
            data=root / "data",
            outputs=root / "outputs",
            frontend=root / "frontend-dashboard",
        )


PATHS = ProjectPaths.from_root(Path(__file__).resolve().parents[2])
