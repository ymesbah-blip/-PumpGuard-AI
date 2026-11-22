# PumpGuard-AI: download, verify and extract the Paderborn "real3" archives.
#
# Data: Lessmeier, Kimotho, Zimmer, Sextro (2016), KAt-DataCenter, Paderborn University.
# Licence of the original data: CC BY-NC 4.0 (non-commercial use, citation required).
# Source used here: Zenodo mirror, DOI 10.5281/zenodo.15845309 (uploaded by J. van den Hoogen).
# The mirror page says CC BY 4.0, but a copy cannot relax the original licence:
# treat the files as CC BY-NC 4.0 and cite Lessmeier et al.
#
# What it does, for each of the 15 archives in zenodo_real3_manifest.csv:
#   1. download into .\archives (resumes partial downloads, skips complete ones)
#   2. check the size and MD5 against the manifest (re-downloads on mismatch, max 3 tries)
#   3. extract into this folder with Windows tar, or 7-Zip if tar cannot read the archive
#   4. count the .mat files (expected: 4 operating conditions x 20 = 80 per bearing)
# and writes real3_fetch_log.csv. Nothing outside this folder is touched.
#
# Usage: copy this script and zenodo_real3_manifest.csv into your data folder
# (e.g. data\paderborn, which git ignores), then in PowerShell:
#   powershell -ExecutionPolicy Bypass -File data\paderborn\fetch_real3.ps1
# Afterwards, from the repository root:
#   pumpguard paderborn verify data/paderborn --archives data/paderborn/archives

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$archives = Join-Path $root 'archives'
New-Item -ItemType Directory -Force -Path $archives | Out-Null
$manifest = Import-Csv (Join-Path $root 'zenodo_real3_manifest.csv')

$needGB = [math]::Ceiling((($manifest | Measure-Object -Property bytes -Sum).Sum * 4) / 1GB)
$drive = (Get-Item $root).PSDrive
if ($drive.Free -lt $needGB * 1GB) {
    throw "Need about $needGB GB free on $($drive.Name): (archives + extracted files); only $([math]::Round($drive.Free / 1GB, 1)) GB free."
}

$sevenZip = @("$env:ProgramFiles\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1

$log = @()
$i = 0
foreach ($row in $manifest) {
    $i++
    $name = $row.file
    $bearing = [IO.Path]::GetFileNameWithoutExtension($name)
    $dest = Join-Path $archives $name
    $url = "https://zenodo.org/records/15845309/files/$name" + '?download=1'
    $expectedBytes = [int64]$row.bytes
    $md5 = ''
    $ok = $false

    for ($attempt = 1; ($attempt -le 3) -and (-not $ok); $attempt++) {
        $have = 0
        if (Test-Path $dest) { $have = (Get-Item $dest).Length }
        if ($have -gt $expectedBytes) { Remove-Item -Force $dest; $have = 0 }
        if ($have -ne $expectedBytes) {
            Write-Host ("[{0}/15] downloading {1} ({2} MB), attempt {3}" -f $i, $name, [math]::Round($expectedBytes / 1MB), $attempt)
            & curl.exe -L --fail --retry 3 --retry-delay 5 -C - -o $dest $url
            if ($LASTEXITCODE -ne 0) { Write-Warning "curl exit code $LASTEXITCODE for $name"; continue }
        }
        $md5 = (Get-FileHash -Algorithm MD5 -Path $dest).Hash.ToLower()
        if ($md5 -eq $row.md5) {
            $ok = $true
        } else {
            Write-Warning "$name MD5 $md5 does not match $($row.md5); deleting and retrying"
            Remove-Item -Force $dest
        }
    }

    $tool = 'not extracted'
    $matCount = (Get-ChildItem -Path $root -Recurse -Filter "*_${bearing}_*.mat" -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($ok -and $matCount -lt 80) {
        Write-Host ("[{0}/15] extracting {1}" -f $i, $name)
        & tar.exe -xf $dest -C $root
        if ($LASTEXITCODE -eq 0) {
            $tool = 'tar'
        } elseif ($sevenZip) {
            & $sevenZip x -y "-o$root" $dest | Out-Null
            $tool = if ($LASTEXITCODE -eq 0) { '7-Zip' } else { 'FAILED' }
        } else {
            $tool = 'FAILED (tar could not read it and 7-Zip is not installed)'
        }
        $matCount = (Get-ChildItem -Path $root -Recurse -Filter "*_${bearing}_*.mat" | Measure-Object).Count
    } elseif ($ok) {
        $tool = 'already extracted'
    }

    $log += [pscustomobject]@{
        file         = $name
        bytes        = $expectedBytes
        md5_expected = $row.md5
        md5_actual   = $md5
        md5_ok       = $ok
        extracted    = $tool
        mat_files    = $matCount
    }
}

$logPath = Join-Path $root 'real3_fetch_log.csv'
$log | Export-Csv -NoTypeInformation -Path $logPath
$log | Format-Table -AutoSize
$bad = @($log | Where-Object { (-not $_.md5_ok) -or ($_.mat_files -ne 80) })
if ($bad.Count -eq 0) {
    Write-Host "All 15 archives verified and extracted (80 .mat files each). Log: $logPath" -ForegroundColor Green
} else {
    Write-Host "$($bad.Count) archive(s) need attention, see $logPath" -ForegroundColor Yellow
}
