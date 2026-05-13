#requires -Version 5.1
<#
.SYNOPSIS
    Install the coding-cli binary on Windows (PowerShell native).

.DESCRIPTION
    Downloads the published Windows release asset for the host architecture,
    extracts coding-cli.exe into a per-user bin directory, and ensures that
    directory is on the user PATH.

.PARAMETER Version
    Release tag to install (e.g. v0.2.0). Defaults to the latest GitHub release.

.PARAMETER InstallDir
    Destination directory for the binary. Defaults to
    %LOCALAPPDATA%\Programs\coding-cli\bin.

.PARAMETER InstallBaseUrl
    Optional base URL to fetch the release archive from (skips the GitHub API).

.PARAMETER Owner
    GitHub owner/org. Defaults to coding-cli.

.PARAMETER Repo
    GitHub repository. Defaults to coding-cli.

.PARAMETER BinaryName
    Binary base name (without .exe). Defaults to coding-cli.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Version v0.2.0
#>
[CmdletBinding()]
param(
    [string]$Version,
    [string]$InstallDir,
    [string]$InstallBaseUrl,
    [string]$Owner = 'coding-cli',
    [string]$Repo = 'coding-cli',
    [string]$BinaryName = 'coding-cli',
    [string]$GitHubApiVersion = '2026-03-10'
)

$ErrorActionPreference = 'Stop'

function Get-TargetArch {
    switch ($env:PROCESSOR_ARCHITECTURE) {
        'AMD64' { return 'amd64' }
        'ARM64' { return 'arm64' }
        'x86'   { throw "32-bit Windows is not supported (PROCESSOR_ARCHITECTURE=$($env:PROCESSOR_ARCHITECTURE))." }
        default { throw "Unsupported CPU architecture: $($env:PROCESSOR_ARCHITECTURE)" }
    }
}

function Get-AuthToken {
    foreach ($name in 'GITHUB_PAT_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN') {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }
    return $null
}

function Invoke-GitHubApi {
    param([string]$Url)
    $headers = @{
        'Accept'               = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = $GitHubApiVersion
        'User-Agent'           = 'coding-cli-installer'
    }
    $token = Get-AuthToken
    if ($token) {
        $headers['Authorization'] = "Bearer $token"
    }
    return Invoke-RestMethod -Uri $Url -Headers $headers
}

function Resolve-LatestVersion {
    $apiUrl = "https://api.github.com/repos/$Owner/$Repo/releases/latest"
    try {
        $release = Invoke-GitHubApi -Url $apiUrl
    }
    catch {
        if (-not (Get-AuthToken)) {
            throw "Could not resolve latest release tag from $apiUrl. If the repository is private, set GITHUB_PAT_TOKEN, GH_TOKEN, or GITHUB_TOKEN and rerun."
        }
        throw "Could not resolve latest release tag from ${apiUrl}: $($_.Exception.Message)"
    }
    return $release.tag_name
}

function Save-ReleaseAsset {
    param([string]$Url, [string]$Destination)
    $headers = @{
        'User-Agent' = 'coding-cli-installer'
    }
    $token = Get-AuthToken
    if ($token) {
        $headers['Authorization'] = "Bearer $token"
    }
    Invoke-WebRequest -Uri $Url -Headers $headers -OutFile $Destination -UseBasicParsing
}

function Add-UserPath {
    param([string]$Directory)
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ([string]::IsNullOrWhiteSpace($current)) {
        [Environment]::SetEnvironmentVariable('Path', $Directory, 'User')
        Write-Host "Added $Directory to user PATH."
        return
    }
    $entries = $current -split ';'
    if ($entries -contains $Directory) {
        return
    }
    [Environment]::SetEnvironmentVariable('Path', "$Directory;$current", 'User')
    Write-Host "Added $Directory to user PATH."
    Write-Host 'Restart your terminal (or open a new shell) to pick up the change.'
}

function Install-CodingCli {
    $arch = Get-TargetArch

    if (-not $InstallDir) {
        $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
        if (-not $localAppData) {
            $localAppData = Join-Path $HOME 'AppData\Local'
        }
        $InstallDir = Join-Path $localAppData 'Programs\coding-cli\bin'
    }

    if (-not $Version -and -not $InstallBaseUrl) {
        $Version = Resolve-LatestVersion
    }

    $assetName = "${BinaryName}_windows_${arch}.zip"
    if ($InstallBaseUrl) {
        $downloadUrl = "$($InstallBaseUrl.TrimEnd('/'))/$assetName"
    }
    else {
        $downloadUrl = "https://github.com/$Owner/$Repo/releases/download/$Version/$assetName"
    }

    $tmpDir = Join-Path ([IO.Path]::GetTempPath()) ("coding-cli-install-" + [Guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
    try {
        $archivePath = Join-Path $tmpDir $assetName
        Write-Host "Downloading $downloadUrl"
        Save-ReleaseAsset -Url $downloadUrl -Destination $archivePath

        Expand-Archive -LiteralPath $archivePath -DestinationPath $tmpDir -Force

        $binaryName = "$BinaryName.exe"
        $extractedBinary = Join-Path $tmpDir $binaryName
        if (-not (Test-Path -LiteralPath $extractedBinary)) {
            throw "Extracted archive does not contain $binaryName"
        }

        if (-not (Test-Path -LiteralPath $InstallDir)) {
            New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        }
        $destination = Join-Path $InstallDir $binaryName
        Copy-Item -LiteralPath $extractedBinary -Destination $destination -Force

        Add-UserPath -Directory $InstallDir
        Write-Host "Installed $binaryName to $destination"
    }
    finally {
        if (Test-Path -LiteralPath $tmpDir) {
            Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Install-CodingCli
