<#
.SYNOPSIS
    One-Command Production Installer for VEYRA Desktop Application.
    Stage 8 Packaging, Deployment & Windows Release Engineering.

.DESCRIPTION
    Installs VEYRA into the user's local application directory (%LOCALAPPDATA%\Programs\VEYRA).
    Operates completely under standard user privileges without requesting UAC administrator rights.
    Creates Start Menu shortcuts, registers Windows uninstallation entry, and prepares
    isolated user-data directories in %LOCALAPPDATA%\VEYRA.

.PARAMETER InstallDir
    Target directory for immutable application binaries. Defaults to %LOCALAPPDATA%\Programs\VEYRA.

.PARAMETER SourceDir
    Source directory containing built VEYRA distribution files. Defaults to .\dist\VEYRA.

.PARAMETER Silent
    Suppresses console interactive prompts.

.PARAMETER SkipShortcuts
    Skips Start Menu and Desktop shortcut creation.
#>

[CmdletBinding()]
param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\VEYRA",
    [string]$SourceDir = "$PSScriptRoot\dist\VEYRA",
    [switch]$Silent,
    [switch]$SkipShortcuts
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "VEYRA -- ONE-COMMAND WINDOWS INSTALLER (STAGE 8)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Validate Source Distribution
if (-not (Test-Path "$SourceDir\VEYRA.exe")) {
    if ($PSScriptRoot -and (Test-Path "$PSScriptRoot\dist\VEYRA\VEYRA.exe")) {
        $SourceDir = "$PSScriptRoot\dist\VEYRA"
    } elseif (Test-Path ".\dist\VEYRA\VEYRA.exe") {
        $SourceDir = (Resolve-Path ".\dist\VEYRA").Path
    }
}

if (-not (Test-Path "$SourceDir\VEYRA.exe")) {
    Write-Host "[ERROR] Distribution executable not found at: $SourceDir\VEYRA.exe" -ForegroundColor Red
    Write-Host "Please build the release first using: python installer/build_executable.py" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Target installation directory: $InstallDir" -ForegroundColor Green
if (-not (Test-Path $InstallDir)) {
    New-Item -Path $InstallDir -ItemType Directory -Force | Out-Null
}

# 2. Copy Application Files
Write-Host "[2/5] Copying application files to destination..." -ForegroundColor Green
Copy-Item -Path "$SourceDir\*" -Destination $InstallDir -Recurse -Force

# Copy uninstall script into installation folder
if (Test-Path "$PSScriptRoot\uninstall.ps1") {
    Copy-Item -Path "$PSScriptRoot\uninstall.ps1" -Destination "$InstallDir\uninstall.ps1" -Force
}

# 3. Create User Data Directories
Write-Host "[3/5] Initializing user data directories..." -ForegroundColor Green
$AppDataDir = "$env:LOCALAPPDATA\VEYRA"
New-Item -Path "$AppDataDir\data" -ItemType Directory -Force | Out-Null
New-Item -Path "$AppDataDir\logs" -ItemType Directory -Force | Out-Null
New-Item -Path "$AppDataDir\config" -ItemType Directory -Force | Out-Null

$LogFile = "$AppDataDir\logs\install.log"
$InstallDate = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
"[$InstallDate] VEYRA v0.1.0 installed to $InstallDir" | Out-File -FilePath $LogFile -Append -Encoding utf8

# 4. Create Windows Start Menu Shortcut
if (-not $SkipShortcuts) {
    Write-Host "[4/5] Creating Start Menu integration..." -ForegroundColor Green
    $StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\VEYRA.lnk"
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut($StartMenuPath)
    $Shortcut.TargetPath = "$InstallDir\VEYRA.exe"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "VEYRA -- PC Observability & Incident Intelligence"
    $IconPath = "$InstallDir\assets\branding\normal\VEYRA_Normal_Icon.ico"
    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = "$IconPath,0"
    }
    $Shortcut.Save()
}

# 5. Register with Windows Add/Remove Programs (HKCU)
Write-Host "[5/5] Registering Windows application entry..." -ForegroundColor Green
$UninstallRegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VEYRA"
if (-not (Test-Path $UninstallRegKey)) {
    New-Item -Path $UninstallRegKey -Force | Out-Null
}

Set-ItemProperty -Path $UninstallRegKey -Name "DisplayName" -Value "VEYRA"
Set-ItemProperty -Path $UninstallRegKey -Name "DisplayVersion" -Value "0.1.0"
Set-ItemProperty -Path $UninstallRegKey -Name "Publisher" -Value "VEYRA Team"
Set-ItemProperty -Path $UninstallRegKey -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $UninstallRegKey -Name "DisplayIcon" -Value "$InstallDir\VEYRA.exe,0"
Set-ItemProperty -Path $UninstallRegKey -Name "UninstallString" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
Set-ItemProperty -Path $UninstallRegKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $UninstallRegKey -Name "NoRepair" -Value 1 -Type DWord

Write-Host "`nSUCCESS: VEYRA installed successfully!" -ForegroundColor Cyan
Write-Host "Launch with: & '$InstallDir\VEYRA.exe' or run_veyra.bat`n" -ForegroundColor Green
exit 0
