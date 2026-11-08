"""Build the Windows portable app and NSIS installer from a clean environment."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lumen import __version__


def icon():
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, 250, 250), radius=56, fill="#007aff")
    draw.ellipse((117, 49, 207, 139), fill="#b8d9ff")
    draw.rounded_rectangle((53, 50, 84, 200), radius=8, fill="#ffffff")
    draw.rounded_rectangle((53, 170, 203, 200), radius=8, fill="#ffffff")
    image.save(ROOT / "packaging/lumen.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])


def notices():
    destination = ROOT / "build/THIRD_PARTY_NOTICES"
    destination.mkdir(parents=True, exist_ok=True)
    inventory = []
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        inventory.append({"name": name, "version": dist.version,
                          "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", "See package notices")})
        for file in dist.files or []:
            if any(word in Path(str(file)).name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file() and source.stat().st_size < 5 * 1024 * 1024:
                    target = destination / name / str(file).replace("..", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    (destination / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


def installer_manifest(bundle):
    # Uninstall removes only shipped files, never recursively deletes an arbitrary chosen folder.
    lines = []
    for file in sorted(bundle.rglob("*")):
        if file.is_file():
            relative = str(file.relative_to(bundle)).replace("/", "\\")
            lines.append('Delete "$INSTDIR\\' + relative.replace("$", "$$") + '"')
    for folder in sorted((p for p in bundle.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        relative = str(folder.relative_to(bundle)).replace("/", "\\")
        lines.append('RMDir "$INSTDIR\\' + relative.replace("$", "$$") + '"')
    (ROOT / "build/uninstall-files.nsh").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--makensis", required=True)
    parser.add_argument("--app-only", action="store_true", help="Build the app for debugging without compressing release assets")
    parser.add_argument("--package-only", action="store_true", help="Compress an already-built, verified app")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("This packaging profile builds Windows x64. Other platforms use the source distribution.")
    if not args.package_only:
        notices()
        icon()
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "packaging/lumen.spec"],
                       cwd=ROOT, check=True)
    bundle = ROOT / "dist/LUMENScience"
    marker = bundle / ".lumen-installation"
    if args.package_only:
        if marker.read_text(encoding="utf-8") != __version__:
            raise SystemExit("The existing bundle does not match the current version")
    else:
        marker.write_text(__version__, encoding="utf-8")
    if args.app_only:
        print("Desktop app built; release compression skipped")
        return
    installer_manifest(bundle)
    archive = ROOT / "dist" / ("LUMEN-Science-" + __version__ + "-windows-x64-portable.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(bundle.rglob("*")):
            if file.is_file():
                output.write(file, str(Path("LUMENScience") / file.relative_to(bundle)))
    subprocess.run([args.makensis, "/DVERSION=" + __version__, "packaging/windows.nsi"], cwd=ROOT, check=True)
    assets = [archive, ROOT / "dist" / ("LUMEN-Science-" + __version__ + "-windows-x64-setup.exe")]
    checksums = []
    for asset in assets:
        checksums.append(hashlib.file_digest(asset.open("rb"), "sha256").hexdigest() + "  " + asset.name)
    (ROOT / "dist/SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("Desktop assets built: " + ", ".join(a.name for a in assets))


if __name__ == "__main__":
    main()
