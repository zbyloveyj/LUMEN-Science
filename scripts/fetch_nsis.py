"""Fetch the exact NSIS build archive; HTML/error pages never pass the digest check."""
import hashlib
import urllib.request
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tools = root / ".tools"
tools.mkdir(exist_ok=True)
archive = tools / "nsis-3.11.zip"
expected = "c7d27f780ddb6cffb4730138cd1591e841f4b7edb155856901cdf5f214394fa1"
mirrors = ("netix.dl", "phoenixnap.dl", "master.dl", "downloads", "pilotfiber.dl")
for mirror in mirrors:
    if archive.exists() and hashlib.sha256(archive.read_bytes()).hexdigest() == expected:
        break
    url = "https://" + mirror + ".sourceforge.net/project/nsis/NSIS%203/3.11/nsis-3.11.zip"
    try:
        with urllib.request.urlopen(url, timeout=35) as response:
            data = response.read(8 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != expected:
            print("Skipping a response with an unexpected digest from " + mirror)
            continue
        archive.write_bytes(data)
    except OSError as exc:
        print("Mirror unavailable: " + mirror + " (" + type(exc).__name__ + ")")
if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Could not obtain the verified NSIS archive from official mirrors")
with zipfile.ZipFile(archive) as source:
    for member in source.infolist():
        if not (tools / member.filename).resolve().is_relative_to(tools.resolve()):
            raise SystemExit("Unexpected archive path")
    source.extractall(tools)
print("Verified NSIS 3.11 archive extracted")
