"""
VEYRA Standalone Executable Builder.
Stage 8 Packaging & Deployment.

Executes PyInstaller using packaging/veyra.spec to produce a self-contained
Windows desktop application bundle in dist/VEYRA.
Verifies branding asset integrity inside the built bundle.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
spec_path = project_root / "installer" / "veyra.spec"
dist_dir = project_root / "dist"
build_dir = project_root / "build"
output_app_dir = dist_dir / "VEYRA"
exe_path = output_app_dir / "VEYRA.exe"


def build():
    print("=" * 60)
    print("VEYRA STANDALONE EXECUTABLE BUILDER (STAGE 8)")
    print("=" * 60)

    # 1. Clean previous build directories
    print("[1/4] Cleaning previous build artifacts...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    # 2. Execute PyInstaller
    print(f"[2/4] Executing PyInstaller with spec: {spec_path.name}...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path)
    ]
    result = subprocess.run(cmd, cwd=str(project_root))
    if result.returncode != 0:
        print(f"ERROR: PyInstaller build failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    # 3. Verify output binary
    print("[3/4] Verifying generated executable...")
    if not exe_path.exists():
        print(f"ERROR: Expected executable not found at {exe_path}")
        sys.exit(1)
    exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"Generated executable: {exe_path} ({exe_size_mb:.2f} MB)")

    # 4. Verify embedded branding integrity
    print("[4/4] Verifying bundled branding assets inside distribution...")
    bundled_manifest = output_app_dir / "_internal" / "assets" / "branding" / "branding_manifest.json"
    if not bundled_manifest.exists():
        # Check direct assets directory
        bundled_manifest = output_app_dir / "assets" / "branding" / "branding_manifest.json"

    if bundled_manifest.exists():
        print(f"Found bundled manifest: {bundled_manifest}")
    else:
        print("Copying branding assets directly to dist root for installer discovery...")
        target_branding = output_app_dir / "assets" / "branding"
        target_branding.mkdir(parents=True, exist_ok=True)
        shutil.copytree(project_root / "assets" / "branding", target_branding, dirs_exist_ok=True)
        print("Branding assets mirrored to distribution root.")

    print("\nBUILD SUCCESSFUL! Standalone VEYRA application ready in dist/VEYRA.")


if __name__ == "__main__":
    build()
