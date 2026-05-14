#requires -Version 5.1
<#
.SYNOPSIS
    Build the freighthero binary on Windows (PowerShell native).

.DESCRIPTION
    Wraps `go build` to produce dist/<binary>(.exe). When -Archive is passed,
    bundles the binary into the platform-appropriate archive
    (.zip on Windows targets, .tar.gz elsewhere).

.PARAMETER BinaryName
    Binary base name (no extension). Defaults to freighthero.

.PARAMETER OutputDir
    Output directory for the binary/archive. Defaults to <repo>/dist.

.PARAMETER TargetOS
    GOOS override. Defaults to the host GOOS.

.PARAMETER TargetArch
    GOARCH override. Defaults to the host GOARCH.

.PARAMETER Archive
    When set, also produce a release archive in OutputDir.
#>
[CmdletBinding()]
param(
    [string]$BinaryName = 'freighthero',
    [string]$OutputDir,
    [string]$TargetOS,
    [string]$TargetArch,
    [switch]$Archive
)

$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutputDir) {
    $OutputDir = Join-Path $rootDir 'dist'
}
# Resolve host GOOS/GOARCH without letting any inherited GOOS/GOARCH env vars
# shadow them — those are the cross-compile request, not the host fact.
$savedGoos = $env:GOOS
$savedGoarch = $env:GOARCH
try {
    Remove-Item Env:GOOS -ErrorAction SilentlyContinue
    Remove-Item Env:GOARCH -ErrorAction SilentlyContinue
    $hostOS = (& go env GOOS).Trim()
    $hostArch = (& go env GOARCH).Trim()
}
finally {
    if ($null -ne $savedGoos)   { $env:GOOS = $savedGoos }
    if ($null -ne $savedGoarch) { $env:GOARCH = $savedGoarch }
}

if (-not $TargetOS)   { $TargetOS = $hostOS }
if (-not $TargetArch) { $TargetArch = $hostArch }
$crossCompile = ($TargetOS -ne $hostOS) -or ($TargetArch -ne $hostArch)

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Push-Location $rootDir
try {
    $binarySuffix = ''
    if ($TargetOS -eq 'windows') {
        $binarySuffix = '.exe'
    }

    $binaryBasename = "$BinaryName$binarySuffix"
    if ($crossCompile) {
        $binaryPath = Join-Path $OutputDir "${BinaryName}_${TargetOS}_${TargetArch}${binarySuffix}"
    }
    else {
        $binaryPath = Join-Path $OutputDir $binaryBasename
    }

    $env:CGO_ENABLED = '0'
    $env:GOOS = $TargetOS
    $env:GOARCH = $TargetArch
    & go build -o $binaryPath .
    if ($LASTEXITCODE -ne 0) {
        throw "go build failed with exit code $LASTEXITCODE"
    }

    if ($Archive.IsPresent) {
        $stagingDir = Join-Path ([IO.Path]::GetTempPath()) ("freighthero-build-" + [Guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $stagingDir | Out-Null
        try {
            Copy-Item -LiteralPath $binaryPath -Destination (Join-Path $stagingDir $binaryBasename)
            if ($TargetOS -eq 'windows') {
                $archivePath = Join-Path $OutputDir "${BinaryName}_${TargetOS}_${TargetArch}.zip"
                if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
                Compress-Archive -Path (Join-Path $stagingDir $binaryBasename) -DestinationPath $archivePath
            }
            else {
                $archivePath = Join-Path $OutputDir "${BinaryName}_${TargetOS}_${TargetArch}.tar.gz"
                # tar.exe is available on Windows 10 1803+; falls back to bash tar otherwise.
                $tarCmd = Get-Command tar -ErrorAction SilentlyContinue
                if (-not $tarCmd) {
                    throw 'tar is required to build a tar.gz archive; install tar or run build.sh under a POSIX shell.'
                }
                & tar -C $stagingDir -czf $archivePath $binaryBasename
                if ($LASTEXITCODE -ne 0) {
                    throw "tar failed with exit code $LASTEXITCODE"
                }
            }
            Write-Host "Built $archivePath"
        }
        finally {
            Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    else {
        Write-Host "Built $binaryPath"
    }
}
finally {
    Pop-Location
}
