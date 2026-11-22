from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import pandas as pd


SOURCE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_MASTER = (
    SOURCE_ROOT
    / "tests/fixtures/forecasting/regional_energy_master.csv"
)


class PortableProject:
    def __init__(self, *, seed_production: bool = True) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.seed_production = seed_production
        self._seed()

    def _copy(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _seed(self) -> None:
        self._copy(
            SOURCE_ROOT / "configs/forecasting/production.json",
            self.root / "configs/forecasting/production.json",
        )
        self._copy(
            SOURCE_ROOT / "configs/dashboard/production.json",
            self.root / "configs/dashboard/production.json",
        )
        for name in (
            "regions.csv",
            "region_aliases.csv",
            "region_coordinates.csv",
            "variable_dictionary.csv",
            "customer_groups.csv",
            "source_registry.csv",
            "reference_layer_contract.json",
        ):
            self._copy(
                SOURCE_ROOT / "data/reference" / name,
                self.root / "data/reference" / name,
            )
        self._copy(
            FIXTURE_MASTER,
            self.root
            / "data/processed/master/regional_energy_master.csv",
        )
        quality_path = (
            self.root / "data/processed/master/data_quality_flags.csv"
        )
        quality_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=(
                "dataset_id",
                "region_id",
                "year",
                "flag_type",
                "severity",
                "message",
            )
        ).to_csv(
            quality_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
        )

        frontend = self.root / "frontend-dashboard"
        (frontend / "src/data").mkdir(parents=True, exist_ok=True)
        (frontend / "src").mkdir(parents=True, exist_ok=True)
        (frontend / "package.json").write_text(
            json.dumps({"name": "ecadin-test-frontend", "private": True})
            + "\n",
            encoding="utf-8",
        )
        self._copy(
            SOURCE_ROOT
            / "frontend-dashboard/src/data/indonesia-provinces.json",
            frontend / "src/data/indonesia-provinces.json",
        )
        self._copy(
            SOURCE_ROOT / "frontend-dashboard/vite.config.ts",
            frontend / "vite.config.ts",
        )
        self._copy(
            SOURCE_ROOT / "frontend-dashboard/vercel.json",
            frontend / "vercel.json",
        )
        self._copy(
            SOURCE_ROOT / "frontend-dashboard/src/styles.css",
            frontend / "src/styles.css",
        )
        (frontend / "src/app.tsx").write_text(
            "export const fixture = true;\n",
            encoding="utf-8",
        )

        if self.seed_production:
            fixture_production = SOURCE_ROOT / "tests/fixtures/production"
            for source in fixture_production.rglob("*.csv"):
                relative = source.relative_to(fixture_production)
                self._copy(
                    source,
                    self.root / "outputs/production" / relative,
                )

    def cleanup(self) -> None:
        self._temporary.cleanup()

    def __enter__(self) -> Path:
        return self.root

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.cleanup()


def portable_project() -> Iterator[Path]:
    with PortableProject() as root:
        yield root
