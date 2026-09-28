# VEYRA — Release Engineering, Versioning & Deployment Guide

> **Document Class:** Release Engineering Specification & Release Checklist  
> **Audience:** Maintainers, DevOps Engineers, Release Managers  
> **Target Platform:** Microsoft Windows 10/11 (x64)  
> **Authoritative Repository:** [github.com/SHAZAAN25/Veyra](https://github.com/SHAZAAN25/Veyra)

---

## 1. Versioning Model

VEYRA follows **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`):
- **MAJOR:** Incompatible architectural shifts, database schema breaking changes without automated forward migration, or fundamental contract rewrites.
- **MINOR:** New collectors, additional diagnostic tests, new optimization profiles, or new UI dashboards that maintain backwards-compatible historical schemas.
- **PATCH:** Bug fixes, performance optimizations, security patches, and documentation improvements.

Pre-release candidates are designated as `vX.Y.Z-RC<N>` (e.g., `v0.1.0-RC1`).

---

## 2. Release Prerequisites

To produce a production release build:
1. **OS Environment:** Windows 10 (Version 2004+) or Windows 11 (x64).
2. **Runtime:** Python 3.12+ 64-bit.
3. **Build Dependencies:**
   ```powershell
   pip install psutil pillow pyinstaller pytest
   ```
4. **Clean Git State:**
   ```powershell
   git status
   # Working tree must be completely clean; all tests passing
   ```
5. **Inno Setup Compiler (Optional for Installer EXE):** Inno Setup 6+ (`iscc.exe` in PATH).

---

## 3. Production Build Procedure

### Step 1: Execute Full Regression Suite
Before initiating packaging, verify that all automated unit, integration, and chaos simulation tests pass without error:
```powershell
uv run --with pytest --with psutil python -m pytest tests/ -q
# Expected: 209 passed, 0 failures, 0 errors, 0 skips
```

### Step 2: Build Standalone Executable
Execute the standalone builder:
```powershell
python installer/build_executable.py
```
This script:
- Cleans prior `build/` and `dist/` directories.
- Invokes PyInstaller with `installer/veyra.spec`.
- Enforces **Rule 9** by stripping `simulation/` and `tests/`.
- Verifies output binary `dist/VEYRA/VEYRA.exe` and bundles official locked branding assets.

### Step 3: Generate Release Integrity Manifest
Calculate SHA-256 digests and file sizes for all release artifacts:
```powershell
python tools/generate_release_manifest.py
```
This generates `release_manifest.json` recording cryptographic digests for `install.ps1`, `uninstall.ps1`, `run_veyra.bat`, `installer/installer.iss`, `installer/AppxManifest.xml`, `installer/veyra.spec`, and `dist/VEYRA/VEYRA.exe`.

### Step 4: Compile Inno Setup Installer (If Inno Setup is present)
```powershell
iscc installer/installer.iss
```
Generates standalone setup wizard `dist/Output/VEYRA-Setup-0.1.0.exe`.

---

## 4. Release Verification Checklist

Every Release Candidate must pass the following manual/automated verification matrix prior to publishing:

- [ ] **Full Test Suite:** 209 automated tests pass cleanly in development environment.
- [ ] **Clean Standalone Launch:** `dist/VEYRA/VEYRA.exe` starts without terminal windows or missing DLL errors.
- [ ] **Locked Branding Verified:** Official Cyan normal and Crimson gaming logos display correctly without distortion.
- [ ] **One-Command Installation:** `install.ps1` installs binaries to `%LOCALAPPDATA%\Programs\VEYRA` and registers Windows Add/Remove Programs entry.
- [ ] **One-Command Launch:** `run_veyra.bat` launches the installed application.
- [ ] **Hardware Observability Active:** Real CPU, RAM, disk, and network throughput counters stream from Windows OS APIs.
- [ ] **Unprivileged Operation:** Executable runs as standard user; zero UAC prompts during normal monitoring.
- [ ] **Database Initialization:** `%LOCALAPPDATA%\VEYRA\data\history.sqlite` is created and schema migrations apply atomically.
- [ ] **Offline Execution:** Full telemetry and local diagnostics function with network interfaces disconnected.
- [ ] **Uninstallation:** `uninstall.ps1` purges binaries, registry entries, and shortcuts while **preserving user data by default**.

---

## 5. Artifact Distribution

Official release distributions include:
1. `install.ps1` — Headless automated PowerShell installer.
2. `uninstall.ps1` — Safe uninstaller preserving user data by default.
3. `run_veyra.bat` — Standalone portable launcher.
4. `dist/VEYRA/` — Standalone multi-file application directory.
5. `release_manifest.json` — Cryptographic SHA-256 release manifest.
