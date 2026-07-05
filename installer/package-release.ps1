<#
.SYNOPSIS
    Build the Nexus release archive for YesMan AI.

.DESCRIPTION
    Produces dist\YesManAI-Setup-<version>.zip containing:
      - YesManAI-Setup-<version>.exe   (the Inno Setup installer)
      - READ-ME-FIRST.txt              (what it is, SmartScreen note, source link, checksum)
      - LICENSE                        (MIT)
      - SHA256.txt                     (checksum of the .exe for integrity verification)

    Version is read from installer\YesManAI.iss (#define AppVersion) so it never drifts.

.PARAMETER Build
    Recompile the installer with ISCC before packaging.

.PARAMETER Iscc
    Path to ISCC.exe (default: "D:\Inno Setup 7\ISCC.exe").

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File installer\package-release.ps1 -Build
#>
[CmdletBinding()]
param(
    [switch]$Build,
    [string]$Iscc = "D:\Inno Setup 7\ISCC.exe"
)

$ErrorActionPreference = "Stop"

# --- Locate repo root (this script lives in <root>\installer) ---
$RepoRoot = Split-Path -Parent $PSScriptRoot
$IssPath  = Join-Path $PSScriptRoot "YesManAI.iss"
$DistDir  = Join-Path $RepoRoot "dist"
$License  = Join-Path $RepoRoot "LICENSE"
$GithubUrl = "https://github.com/JmyX420/YesMan-AI"

if (-not (Test-Path $IssPath))    { throw "Cannot find $IssPath" }
if (-not (Test-Path $License))    { throw "Cannot find $License" }

# --- Read version from the .iss ---
$verMatch = Select-String -Path $IssPath -Pattern '#define\s+AppVersion\s+"([^"]+)"'
if (-not $verMatch) { throw "Could not read AppVersion from $IssPath" }
$Version = $verMatch.Matches[0].Groups[1].Value
Write-Host "Version: $Version" -ForegroundColor Cyan

$ExeName = "YesManAI-Setup-$Version.exe"
$ExePath = Join-Path $DistDir $ExeName

# --- Optionally (re)build the installer ---
if ($Build) {
    if (-not (Test-Path $Iscc)) { throw "ISCC.exe not found at '$Iscc' (pass -Iscc <path>)" }
    Write-Host "Compiling installer..." -ForegroundColor Cyan
    & $Iscc $IssPath
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path $ExePath)) {
    throw "Installer not found: $ExePath`nRun with -Build to compile it first."
}

# --- Compute checksum ---
$Sha = (Get-FileHash -Algorithm SHA256 -Path $ExePath).Hash.ToLower()
$ExeSize = "{0:N2} MB" -f ((Get-Item $ExePath).Length / 1MB)
Write-Host "SHA256: $Sha" -ForegroundColor Cyan

# --- Assemble a clean staging folder ---
$Stage = Join-Path $DistDir "_stage-$Version"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Path $Stage | Out-Null

Copy-Item $ExePath  (Join-Path $Stage $ExeName)
Copy-Item $License  (Join-Path $Stage "LICENSE")

# SHA256.txt (sha256sum-compatible: "<hash>  <filename>")
"$Sha  $ExeName" | Set-Content -Path (Join-Path $Stage "SHA256.txt") -Encoding ASCII

# READ-ME-FIRST.txt
$Readme = @"
YesMan AI - A FNV Modding Toolbox for Claude and Codex
Version $Version
======================================================

WHAT THIS IS
  A single Windows installer that sets up an AI-assisted Fallout: New Vegas
  modding workshop for Claude Code and/or OpenAI Codex. It is NOT a game mod --
  do not install it with Vortex or Mod Organizer. Run the .exe on your PC.

HOW TO INSTALL
  1. Make sure you have Claude Code and/or Codex, plus Node.js and Python 3
     (tick "Add to PATH" when installing Python).
  2. Run  $ExeName  and follow the wizard. It auto-detects your Fallout: New
     Vegas folder, asks which agent to set up, and lets you pick the Mod
     Organizer 2 instance that manages it (or "I don't use MO2").
  3. Restart your agent (and MO2, if you use it). See the Nexus page / README
     for the full first-session steps.

WINDOWS SMARTSCREEN
  This installer is not code-signed (a certificate costs money; this is a free,
  open-source MIT tool). Windows SmartScreen may show a blue
  "Windows protected your PC" dialog. To proceed:
      Click "More info"  ->  "Run anyway".
  This is expected for unsigned installers. Your antivirus may also scan it --
  that is normal.

VERIFY THE DOWNLOAD (optional but recommended)
  The file's SHA-256 checksum is in SHA256.txt. To verify in PowerShell:
      Get-FileHash -Algorithm SHA256 .\$ExeName
  It should match:
      $Sha
  ($ExeName, $ExeSize)

SOURCE CODE
  This is fully open source (MIT). Read every line before you run it:
      $GithubUrl

LICENSE
  MIT. See LICENSE. Adapted from the Skyrim Claude Code Toolkit by
  WingedGuardian, with a bundled FNV MO2 MCP (after Aaronavich's MO2 MCP
  Server) and the YesMan AI Live Link (after Jarvann's SkyLink AI concept).

By JmyX.
"@
# Write with CRLF for Notepad-friendliness
$Readme = $Readme -replace "`r?`n", "`r`n"
Set-Content -Path (Join-Path $Stage "READ-ME-FIRST.txt") -Value $Readme -Encoding UTF8 -NoNewline

# --- Zip it ---
$ZipPath = Join-Path $DistDir "YesManAI-Setup-$Version.zip"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal

Remove-Item -Recurse -Force $Stage

Write-Host ""
Write-Host "Release archive ready:" -ForegroundColor Green
Write-Host "  $ZipPath"
Write-Host ""
Write-Host "Contents:" -ForegroundColor Green
Write-Host "  $ExeName  ($ExeSize)"
Write-Host "  READ-ME-FIRST.txt"
Write-Host "  LICENSE"
Write-Host "  SHA256.txt   ($Sha)"
