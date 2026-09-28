<#
.SYNOPSIS
    Uninstaller for VEYRA Desktop Application.
    Stage 8 Packaging & Deployment.

.DESCRIPTION
    Removes application binaries, Start Menu shortcuts, and Windows uninstaller registry keys.
    PRESERVES USER DATA (%LOCALAPPDATA%\VEYRA) BY DEFAULT.
    User data is purged ONLY if -PurgeData switch is explicitly provided.
#>

[CmdletBinding()]
param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\VEYRA",
    [switch]$PurgeData,
    [switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "VEYRA -- APPLICATION UNINSTALLER (STAGE 8)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Terminate running instances
Write-Host "[1/4] Stopping running VEYRA instances..." -ForegroundColor Green
Get-Process -Name "VEYRA" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Remove Start Menu & Desktop Shortcuts
Write-Host "[2/4] Removing shortcuts..." -ForegroundColor Green
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\VEYRA.lnk"
if (Test-Path $StartMenuPath) {
    Remove-Item -Path $StartMenuPath -Force -ErrorAction SilentlyContinue
}
$DesktopPath = "$env:USERPROFILE\Desktop\VEYRA.lnk"
if (Test-Path $DesktopPath) {
    Remove-Item -Path $DesktopPath -Force -ErrorAction SilentlyContinue
}

# 3. Remove Windows Add/Remove Programs Registration
Write-Host "[3/4] Removing registry entries..." -ForegroundColor Green
$UninstallRegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VEYRA"
if (Test-Path $UninstallRegKey) {
    Remove-Item -Path $UninstallRegKey -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Remove Application Binaries
Write-Host "[4/4] Removing application binaries from $InstallDir..." -ForegroundColor Green
if (Test-Path $InstallDir) {
    Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
}

# User Data Policy: Preserved by default
$UserDataDir = "$env:LOCALAPPDATA\VEYRA"
if ($PurgeData) {
    Write-Host "[DATA POLICY] Purging user data and historical records..." -ForegroundColor Yellow
    if (Test-Path $UserDataDir) {
        Remove-Item -Path $UserDataDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "All user data purged." -ForegroundColor Yellow
} else {
    Write-Host "[DATA POLICY] User history and records PRESERVED in $UserDataDir" -ForegroundColor Cyan
}

Write-Host "`nSUCCESS: VEYRA has been uninstalled." -ForegroundColor Green
exit 0
