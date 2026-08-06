param(
    [string]$ProjectRoot = "D:\ECADIN_Project_Clean"
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $ProjectRoot "migration\backups\phase2c_distributed_electricity_$timestamp"

$copies = @(
    @{
        Source = "distributed_electricity.py"
        Destination = "src\ecadin_energy\data_processing\cleaning\distributed_electricity.py"
    },
    @{
        Source = "build_distributed_electricity.py"
        Destination = "scripts\build_distributed_electricity.py"
    },
    @{
        Source = "validate_distributed_electricity.py"
        Destination = "scripts\validate_distributed_electricity.py"
    },
    @{
        Source = "test_distributed_electricity.py"
        Destination = "tests\unit\test_distributed_electricity.py"
    },
    @{
        Source = "distributed_electricity.md"
        Destination = "docs\data\distributed_electricity.md"
    }
)

foreach ($copy in $copies) {
    $source = Join-Path $PackageRoot $copy.Source
    $destination = Join-Path $ProjectRoot $copy.Destination
    $destinationDir = Split-Path $destination -Parent

    if (-not (Test-Path $source -PathType Leaf)) {
        throw "Package file tidak ditemukan: $source"
    }

    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null

    if (Test-Path $destination -PathType Leaf) {
        $relative = $copy.Destination
        $backup = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Path (Split-Path $backup -Parent) -Force |
            Out-Null
        Copy-Item $destination $backup -Force
    }

    Copy-Item $source $destination -Force
}

$reviewDir = Join-Path $ProjectRoot "migration\demand\distributed_electricity"
New-Item -ItemType Directory -Path $reviewDir -Force | Out-Null

$reviewFiles = @(
    "ECADIN_distributed_electricity_raw_audit.xlsx",
    "expected_raw_audit.csv",
    "README_PHASE2C.md"
)

foreach ($file in $reviewFiles) {
    Copy-Item `
        -Path (Join-Path $PackageRoot $file) `
        -Destination (Join-Path $reviewDir $file) `
        -Force
}

Write-Host ""
Write-Host "PHASE 2C CLEANER INSTALLED" -ForegroundColor Green
Write-Host "Project root : $ProjectRoot"
if (Test-Path $backupRoot) {
    Write-Host "Backup       : $backupRoot"
}
Write-Host ""
Write-Host "Run:"
Write-Host "  python .\scripts\build_distributed_electricity.py"
Write-Host "  python .\scripts\validate_distributed_electricity.py"
