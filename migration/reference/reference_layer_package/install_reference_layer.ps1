param(
    [string]$ProjectRoot = "D:\ECADIN_Project_Clean"
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$referenceDir = Join-Path $ProjectRoot "data\reference"
$harmonizationDir = Join-Path $ProjectRoot "src\ecadin_energy\data_processing\harmonization"
$scriptsDir = Join-Path $ProjectRoot "scripts"
$reportDir = Join-Path $ProjectRoot "migration\reference"

New-Item -ItemType Directory -Path $referenceDir -Force | Out-Null
New-Item -ItemType Directory -Path $harmonizationDir -Force | Out-Null
New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$referenceFiles = @(
    "regions.csv",
    "region_aliases.csv",
    "region_coordinates.csv",
    "variable_dictionary.csv",
    "reference_layer_contract.json"
)

foreach ($file in $referenceFiles) {
    Copy-Item `
        -Path (Join-Path $PackageRoot $file) `
        -Destination (Join-Path $referenceDir $file) `
        -Force
}

Copy-Item `
    -Path (Join-Path $PackageRoot "regions.py") `
    -Destination (Join-Path $harmonizationDir "regions.py") `
    -Force

Copy-Item `
    -Path (Join-Path $PackageRoot "validate_reference_layer.py") `
    -Destination (Join-Path $scriptsDir "validate_reference_layer.py") `
    -Force

$reviewFiles = @(
    "reference_source_comparison.csv",
    "geometry_audit.csv",
    "ECADIN_reference_layer_review.xlsx",
    "README_REFERENCE_LAYER.md"
)

foreach ($file in $reviewFiles) {
    Copy-Item `
        -Path (Join-Path $PackageRoot $file) `
        -Destination (Join-Path $reportDir $file) `
        -Force
}

Write-Host ""
Write-Host "REFERENCE LAYER INSTALLED" -ForegroundColor Green
Write-Host "Project root : $ProjectRoot"
Write-Host "Reference    : $referenceDir"
Write-Host ""
Write-Host "Validate with:"
Write-Host "  python .\scripts\validate_reference_layer.py"
