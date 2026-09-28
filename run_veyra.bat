@echo off
rem =====================================================================
rem VEYRA — One-Command Production Launcher
rem Stage 8 Packaging, Deployment & Windows Release Engineering
rem =====================================================================

setlocal enabledelayedexpansion

set "INSTALLED_EXE=%LOCALAPPDATA%\Programs\VEYRA\VEYRA.exe"
set "DIST_EXE=%~dp0dist\VEYRA\VEYRA.exe"

if exist "!INSTALLED_EXE!" (
    echo Starting installed VEYRA Desktop Application...
    start "" "!INSTALLED_EXE!" %*
    exit /b 0
)

if exist "!DIST_EXE!" (
    echo Starting packaged VEYRA Desktop Application from distribution...
    start "" "!DIST_EXE!" %*
    exit /b 0
)

echo.
echo =====================================================================
echo ERROR: VEYRA executable was not found.
echo =====================================================================
echo.
echo Checked locations:
echo   1. !INSTALLED_EXE!
echo   2. !DIST_EXE!
echo.
echo Please install VEYRA first:
echo   Run in PowerShell: .\install.ps1
echo.
exit /b 1
