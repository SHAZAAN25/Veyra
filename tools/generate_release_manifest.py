"""
VEYRA Release Manifest Generator.
Stage 8 Packaging & Release Engineering.

Scans release artifacts in dist/ and installer scripts, computes cryptographic
SHA-256 digests, records byte sizes, and writes release_manifest.json.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, List

project_root = Path(__file__).resolve().parent.parent
dist_dir = project_root / "dist"
manifest_out = project_root / "release_manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest() -> Dict[str, Any]:
    artifacts: List[Dict[str, Any]] = []

    # Important deployment files
    root_artifacts = [
        "install.ps1",
        "uninstall.ps1",
        "run_veyra.bat",
        "installer/installer.iss",
        "installer/AppxManifest.xml",
        "installer/veyra.spec",
    ]

    for rel_path in root_artifacts:
        full_path = project_root / rel_path
        if full_path.exists():
            artifacts.append({
                "name": rel_path.replace("\\", "/"),
                "file_size_bytes": full_path.stat().st_size,
                "sha256": sha256_file(full_path),
                "artifact_type": "deployment_script" if rel_path.endswith((".ps1", ".bat")) else "installer_spec"
            })

    # Built binaries if available
    exe_path = dist_dir / "VEYRA" / "VEYRA.exe"
    if exe_path.exists():
        artifacts.append({
            "name": "dist/VEYRA/VEYRA.exe",
            "file_size_bytes": exe_path.stat().st_size,
            "sha256": sha256_file(exe_path),
            "artifact_type": "standalone_binary"
        })

    installer_path = dist_dir / "installer" / "VEYRA_Setup_v0.1.0.exe"
    if installer_path.exists():
        artifacts.append({
            "name": "dist/installer/VEYRA_Setup_v0.1.0.exe",
            "file_size_bytes": installer_path.stat().st_size,
            "sha256": sha256_file(installer_path),
            "artifact_type": "windows_installer"
        })

    manifest = {
        "product": "VEYRA",
        "version": "0.1.0",
        "release_channel": "stable",
        "architecture": "x64",
        "hash_algorithm": "SHA-256",
        "generated_by": "tools/generate_release_manifest.py",
        "artifact_count": len(artifacts),
        "artifacts": artifacts
    }

    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Release manifest generated at: {manifest_out}")
    print(f"Total tracked release artifacts: {len(artifacts)}")
    return manifest


if __name__ == "__main__":
    generate_manifest()
