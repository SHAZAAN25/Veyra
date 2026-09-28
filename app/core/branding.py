"""
VEYRA Branding Integrity Verification Engine.
Enforces the immutable lock on official VEYRA branding assets.
"""
import hashlib
import json
import os
import struct
from dataclasses import dataclass
import sys
from pathlib import Path

# Ensure project root is in sys.path when invoked directly as a script
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.core.exceptions import BrandingIntegrityError


@dataclass
class VerificationFailure:
    asset_path: str
    failure_type: str  # "MISSING", "HASH_MISMATCH", "UNREADABLE", "DIMENSION_MISMATCH"
    expected_sha256: Optional[str] = None
    actual_sha256: Optional[str] = None
    details: str = ""


@dataclass
class VerificationReport:
    is_valid: bool
    verified_count: int
    failures: List[VerificationFailure]
    manifest_version: str

    def print_summary(self) -> str:
        if self.is_valid:
            return f"BRANDING VERIFICATION PASSED: All {self.verified_count} assets intact."
        lines = [f"BRANDING VERIFICATION FAILED: {len(self.failures)} issue(s) detected:"]
        for f in self.failures:
            lines.append(f"  - [{f.failure_type}] {f.asset_path}")
            if f.expected_sha256 and f.actual_sha256:
                lines.append(f"      Expected SHA-256: {f.expected_sha256}")
                lines.append(f"      Actual SHA-256:   {f.actual_sha256}")
            if f.details:
                lines.append(f"      Details: {f.details}")
        return "\n".join(lines)


def calculate_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of file contents."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_png_dimensions(path: Path) -> Optional[List[int]]:
    """Inspect PNG header to obtain width and height without third-party dependencies."""
    try:
        with open(path, "rb") as f:
            header = f.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                w, h = struct.unpack(">II", header[16:24])
                return [w, h]
    except Exception:
        pass
    return None


def verify_branding_manifest(
    project_root: Optional[Path] = None,
    raise_on_error: bool = False
) -> VerificationReport:
    """
    Verifies that all assets recorded in the branding manifest are present,
    unmodified, readable, and matching their recorded SHA-256 signatures.
    """
    if project_root is None:
        try:
            from app.core.paths import get_installation_dir
            project_root = get_installation_dir()
        except Exception:
            project_root = Path(__file__).resolve().parent.parent.parent

    manifest_path = project_root / "assets" / "branding" / "branding_manifest.json"
    if not manifest_path.exists() and getattr(sys, "frozen", False):
        exe_manifest = Path(sys.executable).parent / "assets" / "branding" / "branding_manifest.json"
        if exe_manifest.exists():
            manifest_path = exe_manifest
            project_root = Path(sys.executable).parent

    if not manifest_path.exists():
        failure = VerificationFailure(
            asset_path=str(manifest_path),
            failure_type="MISSING",
            details="branding_manifest.json does not exist."
        )
        report = VerificationReport(
            is_valid=False,
            verified_count=0,
            failures=[failure],
            manifest_version="unknown"
        )
        if raise_on_error:
            raise BrandingIntegrityError("Branding manifest is missing.", details={"manifest": str(manifest_path)})
        return report

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception as e:
        failure = VerificationFailure(
            asset_path=str(manifest_path),
            failure_type="UNREADABLE",
            details=f"Could not read manifest JSON: {e}"
        )
        report = VerificationReport(
            is_valid=False,
            verified_count=0,
            failures=[failure],
            manifest_version="invalid"
        )
        if raise_on_error:
            raise BrandingIntegrityError(f"Corrupt manifest: {e}")
        return report

    assets = manifest_data.get("assets", [])
    failures: List[VerificationFailure] = []
    verified_count = 0

    for asset_entry in assets:
        rel_path = asset_entry.get("asset_path")
        expected_sha = asset_entry.get("sha256")
        expected_dims = asset_entry.get("dimensions")
        file_path = project_root / rel_path

        if not file_path.exists():
            failures.append(VerificationFailure(
                asset_path=rel_path,
                failure_type="MISSING",
                expected_sha256=expected_sha,
                details=f"Asset not found at {file_path}"
            ))
            continue

        try:
            actual_sha = calculate_sha256(file_path)
        except Exception as e:
            failures.append(VerificationFailure(
                asset_path=rel_path,
                failure_type="UNREADABLE",
                expected_sha256=expected_sha,
                details=f"Error reading asset: {e}"
            ))
            continue

        if actual_sha != expected_sha:
            failures.append(VerificationFailure(
                asset_path=rel_path,
                failure_type="HASH_MISMATCH",
                expected_sha256=expected_sha,
                actual_sha256=actual_sha,
                details="SHA-256 checksum does not match locked brand record."
            ))
            continue

        # Optional dimension check for PNGs
        if expected_dims and file_path.suffix.lower() == ".png":
            actual_dims = get_png_dimensions(file_path)
            if actual_dims != expected_dims:
                failures.append(VerificationFailure(
                    asset_path=rel_path,
                    failure_type="DIMENSION_MISMATCH",
                    expected_sha256=expected_sha,
                    actual_sha256=actual_sha,
                    details=f"Expected dimensions {expected_dims}, got {actual_dims}"
                ))
                continue

        verified_count += 1

    is_valid = len(failures) == 0
    report = VerificationReport(
        is_valid=is_valid,
        verified_count=verified_count,
        failures=failures,
        manifest_version=manifest_data.get("manifest_version", "1.0.0")
    )

    if not is_valid and raise_on_error:
        raise BrandingIntegrityError(
            report.print_summary(),
            details={"failures": [f.__dict__ for f in failures]}
        )

    return report


if __name__ == "__main__":
    rep = verify_branding_manifest()
    print(rep.print_summary())
    if not rep.is_valid:
        exit(1)
