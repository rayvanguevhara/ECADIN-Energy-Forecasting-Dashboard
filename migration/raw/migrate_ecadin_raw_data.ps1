param(
    [string]$LegacyRoot = "D:\ECADIN Project",
    [string]$CleanRoot = "D:\ECADIN_Project_Clean",
    [string]$PlanPath = "D:\ECADIN_Project_Clean\migration\raw\ECADIN_raw_migration_plan.csv",
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PlanPath)) {
    throw "Migration plan tidak ditemukan: $PlanPath"
}

$plan = Import-Csv $PlanPath | Where-Object { $_.Decision -eq "copy_raw" }

if (-not $plan) {
    throw "Tidak ada baris copy_raw pada migration plan."
}

$manifestDir = Join-Path $CleanRoot "migration\raw"
New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$manifestPath = Join-Path $manifestDir "raw_copy_manifest_$timestamp.csv"

$seenHashes = @{}
$results = New-Object System.Collections.Generic.List[object]

foreach ($item in $plan) {
    $source = $item.FullPath

    if (-not $source.StartsWith($LegacyRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $results.Add([PSCustomObject]@{
            DatasetID  = $item.DatasetID
            Source      = $source
            Destination = ""
            SHA256      = ""
            SizeBytes   = ""
            Status      = "rejected_outside_legacy_root"
            Message     = "Source berada di luar LegacyRoot."
        })
        continue
    }

    if (-not (Test-Path $source -PathType Leaf)) {
        $results.Add([PSCustomObject]@{
            DatasetID  = $item.DatasetID
            Source      = $source
            Destination = ""
            SHA256      = ""
            SizeBytes   = ""
            Status      = "source_missing"
            Message     = "File sumber tidak ditemukan."
        })
        continue
    }

    $destinationDir = Join-Path $CleanRoot $item.DestinationDirectory
    $destination = Join-Path $destinationDir $item.FileName
    $sourceHash = (Get-FileHash $source -Algorithm SHA256).Hash
    $sizeBytes = (Get-Item $source).Length

    if ($seenHashes.ContainsKey($sourceHash)) {
        $results.Add([PSCustomObject]@{
            DatasetID  = $item.DatasetID
            Source      = $source
            Destination = $destination
            SHA256      = $sourceHash
            SizeBytes   = $sizeBytes
            Status      = "skipped_duplicate_content"
            Message     = "Konten identik dengan: $($seenHashes[$sourceHash])"
        })
        continue
    }

    $seenHashes[$sourceHash] = $source

    if ($DryRun) {
        $results.Add([PSCustomObject]@{
            DatasetID  = $item.DatasetID
            Source      = $source
            Destination = $destination
            SHA256      = $sourceHash
            SizeBytes   = $sizeBytes
            Status      = "dry_run"
            Message     = "Tidak ada file yang disalin."
        })
        continue
    }

    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null

    if (Test-Path $destination -PathType Leaf) {
        $destinationHash = (Get-FileHash $destination -Algorithm SHA256).Hash

        if ($destinationHash -eq $sourceHash) {
            $results.Add([PSCustomObject]@{
                DatasetID  = $item.DatasetID
                Source      = $source
                Destination = $destination
                SHA256      = $sourceHash
                SizeBytes   = $sizeBytes
                Status      = "already_present_verified"
                Message     = "Target sudah ada dan hash sama."
            })
            continue
        }

        if (-not $Force) {
            $results.Add([PSCustomObject]@{
                DatasetID  = $item.DatasetID
                Source      = $source
                Destination = $destination
                SHA256      = $sourceHash
                SizeBytes   = $sizeBytes
                Status      = "conflict_not_overwritten"
                Message     = "Target ada dengan hash berbeda. Gunakan -Force setelah review."
            })
            continue
        }
    }

    Copy-Item -Path $source -Destination $destination -Force:$Force
    $copiedHash = (Get-FileHash $destination -Algorithm SHA256).Hash

    if ($copiedHash -ne $sourceHash) {
        throw "Hash verification gagal: $destination"
    }

    $results.Add([PSCustomObject]@{
        DatasetID  = $item.DatasetID
        Source      = $source
        Destination = $destination
        SHA256      = $sourceHash
        SizeBytes   = $sizeBytes
        Status      = "copied_verified"
        Message     = "Copy selesai dan SHA256 sesuai."
    })
}

$results |
    Export-Csv -Path $manifestPath -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "RAW MIGRATION SUMMARY" -ForegroundColor Cyan
$results |
    Group-Object Status |
    Sort-Object Name |
    Format-Table Name, Count -AutoSize

Write-Host "Manifest: $manifestPath" -ForegroundColor Green

$bad = $results | Where-Object {
    $_.Status -in @(
        "source_missing",
        "rejected_outside_legacy_root",
        "conflict_not_overwritten"
    )
}

if ($bad) {
    Write-Warning "Migrasi selesai dengan item yang perlu direview."
    exit 1
}

exit 0
