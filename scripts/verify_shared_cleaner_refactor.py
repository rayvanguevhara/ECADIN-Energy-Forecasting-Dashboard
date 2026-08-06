from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from ecadin_energy.data_processing.cleaning.distributed_electricity import (
    build_distributed_electricity,
    validate_distributed_electricity,
)
from ecadin_energy.data_processing.cleaning.local_generation import (
    build_local_generation,
    validate_local_generation,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    baseline_path = (
        project_root
        / "migration/cleaning/shared_refactor/pre_refactor_output_hashes.csv"
    )
    post_path = (
        project_root
        / "migration/cleaning/shared_refactor/post_refactor_output_hashes.csv"
    )

    if not baseline_path.is_file():
        raise FileNotFoundError(f"Baseline hash manifest not found: {baseline_path}")

    # Canonical build order is intentional because the shared lineage and quality
    # tables preserve dataset blocks in pipeline order.
    demand_summary = build_distributed_electricity(project_root=project_root)
    demand_validation = validate_distributed_electricity(project_root=project_root)
    supply_summary = build_local_generation(project_root=project_root)
    supply_validation = validate_local_generation(project_root=project_root)

    with baseline_path.open("r", encoding="utf-8-sig", newline="") as handle:
        baseline_rows = list(csv.DictReader(handle))

    comparison_rows: list[dict[str, object]] = []
    failures: list[str] = []

    for row in baseline_rows:
        relative_path = row["RelativePath"].replace("\\", "/")
        output_path = project_root / relative_path
        if not output_path.is_file():
            failures.append(f"Missing output: {relative_path}")
            comparison_rows.append(
                {
                    "RelativePath": relative_path,
                    "ExpectedSHA256": row["SHA256"],
                    "ActualSHA256": "",
                    "ExpectedSizeBytes": row["SizeBytes"],
                    "ActualSizeBytes": "",
                    "HashEqual": False,
                    "SizeEqual": False,
                }
            )
            continue

        actual_hash = sha256_file(output_path)
        actual_size = output_path.stat().st_size
        hash_equal = actual_hash == row["SHA256"].upper()
        size_equal = actual_size == int(row["SizeBytes"])

        if not hash_equal:
            failures.append(f"SHA-256 mismatch: {relative_path}")
        if not size_equal:
            failures.append(f"Size mismatch: {relative_path}")

        comparison_rows.append(
            {
                "RelativePath": relative_path,
                "ExpectedSHA256": row["SHA256"].upper(),
                "ActualSHA256": actual_hash,
                "ExpectedSizeBytes": row["SizeBytes"],
                "ActualSizeBytes": actual_size,
                "HashEqual": hash_equal,
                "SizeEqual": size_equal,
            }
        )

    post_path.parent.mkdir(parents=True, exist_ok=True)
    with post_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    print("ECADIN SHARED CLEANER REFACTOR VERIFICATION")
    print("=" * 72)
    print(
        f"Demand contract : {demand_validation['canonical_rows']} rows, "
        f"{demand_validation['quality_flags']} quality flags"
    )
    print(
        f"Supply contract : {supply_validation['canonical_rows']} rows, "
        f"{supply_validation['quality_flags']} quality flags"
    )
    print()
    for row in comparison_rows:
        status = "PASS" if row["HashEqual"] and row["SizeEqual"] else "FAIL"
        print(f"[{status}] {row['RelativePath']}")
    print()
    print(f"Comparison report: {post_path}")

    if failures:
        print("\nVerification failures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nAll six production output contracts are byte-for-byte unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
