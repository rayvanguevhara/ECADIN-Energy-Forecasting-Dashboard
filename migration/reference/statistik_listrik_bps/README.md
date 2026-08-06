# ECADIN Statistik Listrik BPS Audit

The migration phase label appears only in the ZIP filename. Internal package
files and installed project paths use functional names.

## Dependency

```powershell
python -c "import fitz; print(fitz.VersionBind)"
```

When the import fails:

```powershell
python -m pip install -r `
  ".\migration\reference\statistik_listrik_bps_package\requirements_statistik_listrik_bps.txt"
```

## Install

```powershell
PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\reference\statistik_listrik_bps_package\install_statistik_listrik_bps.ps1" `
  -ProjectRoot "D:\ECADIN_Project_Clean"
```

## Run

```powershell
python .\scripts\audit_statistik_listrik_bps.py
python .\scripts\validate_statistik_listrik_bps.py
```

## Expected contract

- PDF files: 16
- usable text layers: 16
- operational-region publications: 2
- province publications: 14
- latest table inventory: 57
- regional comparisons: 510
- exact regional matches: 478
- regional revision candidates: 30
- missing-versus-zero reviews: 2
- national total rows: 15
- national revision candidates: 2
- canonical outputs modified: no
- automatic revision applied: no
