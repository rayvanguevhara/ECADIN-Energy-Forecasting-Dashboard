param(
    [string]$LegacyRoot = "D:\ECADIN Project",
    [string]$CleanRoot = "D:\ECADIN_Project_Clean",
    [string]$SelectionPath = "D:\ECADIN_Project_Clean\migration\reference\ECADIN_reference_candidate_selection.csv"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SelectionPath)) {
    throw "Selection manifest tidak ditemukan: $SelectionPath"
}

$targetRoot = Join-Path $CleanRoot "migration\reference\candidate_files"
$zipPath = Join-Path $CleanRoot "migration\reference\ECADIN_reference_candidate_files.zip"
$manifestPath = Join-Path $CleanRoot "migration\reference\reference_candidate_copy_manifest.csv"

Remove-Item $targetRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null

$selection = Import-Csv $SelectionPath
$results = New-Object System.Collections.Generic.List[object]

foreach ($item in $selection) {
    $source = $item.FullPath

    if (-not $source.StartsWith($LegacyRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Source di luar legacy root: $source"
    }

    if (-not (Test-Path $source -PathType Leaf)) {
        throw "File kandidat tidak ditemukan: $source"
    }

    $relative = $source.Substring($LegacyRoot.Length).TrimStart("\")
    $destination = Join-Path $targetRoot $relative
    $destinationDir = Split-Path $destination -Parent

    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    Copy-Item -Path $source -Destination $destination -Force

    $sourceHash = (Get-FileHash $source -Algorithm SHA256).Hash
    $destinationHash = (Get-FileHash $destination -Algorithm SHA256).Hash

    if ($sourceHash -ne $destinationHash) {
        throw "Hash tidak cocok setelah copy: $relative"
    }

    $results.Add([PSCustomObject]@{
        ReviewRole = $item.ReviewRole
        RelativePath = $relative
        SizeBytes = (Get-Item $destination).Length
        SHA256 = $destinationHash
        Status = "copied_verified"
    })
}

$results |
    Export-Csv -Path $manifestPath -NoTypeInformation -Encoding UTF8

Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$targetRoot\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "REFERENCE CANDIDATE COLLECTION COMPLETE" -ForegroundColor Green
Write-Host "Files    : $($results.Count)"
Write-Host "Manifest : $manifestPath"
Write-Host "ZIP      : $zipPath"
