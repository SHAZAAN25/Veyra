"""
Branding Manifest Generator for VEYRA.
Computes SHA-256 hashes and dimensions from actual assets on disk.
"""
import hashlib
import json
import struct
from pathlib import Path


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_png_dimensions(path: Path):
    with open(path, "rb") as f:
        data = f.read(32)
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            w, h = struct.unpack(">II", data[16:24])
            return [w, h]
    return None


def main():
    root = Path(__file__).resolve().parent.parent
    branding_root = root / "assets" / "branding"

    manifest = {
        "manifest_version": "1.0.0",
        "product": "VEYRA",
        "status": "LOCKED",
        "hash_algorithm": "SHA-256",
        "policy": "The artwork must not be redrawn, recreated, traced, vectorized into a different design, recolored, reshaped, distorted, cropped, stretched, filtered, tinted, glowed, blurred, or replaced.",
        "assets": []
    }

    purposes = {
        "VEYRA_Normal_Logo_EXACT.png": "Normal Mode locked master raster artwork",
        "VEYRA_Normal_Logo_EXACT.svg": "Normal Mode locked exact vector container",
        "VEYRA_Normal_Icon.ico": "Normal Mode Windows executable and tray icon",
        "VEYRA_Normal_Logo_1024x1024.png": "Normal Mode high-resolution display artwork",
        "VEYRA_Normal_Logo_512x512.png": "Normal Mode large display artwork",
        "VEYRA_Normal_Logo_256x256.png": "Normal Mode medium-large display artwork",
        "VEYRA_Normal_Logo_128x128.png": "Normal Mode standard UI header artwork",
        "VEYRA_Normal_Logo_64x64.png": "Normal Mode compact UI icon artwork",
        "VEYRA_Normal_Logo_32x32.png": "Normal Mode small UI/status icon artwork",
        "VEYRA_Normal_Logo_SPEC.json": "Normal Mode brand specification metadata",
        "README.txt": "Documentation and asset guidelines",
        "VEYRA_Gaming_Logo_EXACT.png": "Gaming Mode locked master raster artwork",
        "VEYRA_Gaming_Logo_EXACT.svg": "Gaming Mode locked exact vector container",
        "VEYRA_Gaming_Icon.ico": "Gaming Mode Windows executable and tray icon",
        "VEYRA_Gaming_Logo_1024x1024.png": "Gaming Mode high-resolution display artwork",
        "VEYRA_Gaming_Logo_512x512.png": "Gaming Mode large display artwork",
        "VEYRA_Gaming_Logo_256x256.png": "Gaming Mode medium-large display artwork",
        "VEYRA_Gaming_Logo_128x128.png": "Gaming Mode standard UI header artwork",
        "VEYRA_Gaming_Logo_64x64.png": "Gaming Mode compact UI icon artwork",
        "VEYRA_Gaming_Logo_32x32.png": "Gaming Mode small UI/status icon artwork",
        "VEYRA_Gaming_Logo_SPEC.json": "Gaming Mode brand specification metadata",
    }

    for mode in ["normal", "gaming"]:
        dir_path = branding_root / mode
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.iterdir()):
            if not f.is_file():
                continue
            rel_path = f.relative_to(root).as_posix()
            ext = f.suffix.lower().lstrip(".")
            sha = file_hash(f)
            dims = get_png_dimensions(f) if ext == "png" else None
            manifest["assets"].append({
                "asset_path": rel_path,
                "file_name": f.name,
                "mode": mode,
                "file_type": ext,
                "file_size_bytes": f.stat().st_size,
                "dimensions": dims,
                "asset_purpose": purposes.get(f.name, f"{mode.capitalize()} mode asset"),
                "sha256": sha
            })

    out_file = branding_root / "branding_manifest.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated manifest with {len(manifest['assets'])} assets at {out_file}")


if __name__ == "__main__":
    main()
