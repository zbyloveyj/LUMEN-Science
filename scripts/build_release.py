"""Build a source-only release from an explicit allowlist, never runtime state."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE_DIRS=("lumen","web","tests","docs","scripts","packaging",".github")
ROOT_FILES=(".gitattributes","run.py","desktop.py","requirements.txt","requirements-data.txt","requirements-desktop.txt","README.md","README.en.md",
            "LICENSE","CONTRIBUTING.md","SECURITY.md","ROADMAP.md","ACKNOWLEDGEMENTS.md",
            "CHANGELOG.md",".gitignore","启动科研工作台.cmd")
EXTENSIONS={".py",".js",".css",".html",".svg",".md",".txt",".yml",".yaml",".json",".cmd",".ps1",".nsi",".spec"}
EXCLUDED={".state",".vendor",".venv",".build-venv",".tools","build",".git","__pycache__","test-results","dist","node_modules"}


def source_files():
    result=[]
    for name in ROOT_FILES:
        path=ROOT/name
        if not path.is_file():raise ValueError("Required source file missing: "+name)
        result.append(path)
    for directory in SOURCE_DIRS:
        for path in sorted((ROOT/directory).rglob("*")):
            if not path.is_file() or path.is_symlink() or any(p in EXCLUDED for p in path.relative_to(ROOT).parts):
                continue
            if path.suffix.lower() in EXTENSIONS:result.append(path)
    return sorted(set(result))


def audit(files):
    problems=[]
    patterns=[
        (r"sk-[A-Za-z0-9_-]{24,}","possible API credential"),
        (r"gh[pousr]_[A-Za-z0-9]{20,}","possible GitHub credential"),
        (r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----","private key"),
        (r"C:\\Users\\[0-9A-Za-z_-]+\\","private absolute user path"),
    ]
    for path in files:
        if path.stat().st_size>2*1024*1024:
            problems.append(str(path.relative_to(ROOT))+": oversized source file")
        text=path.read_text(encoding="utf-8-sig")
        # The scanner's pattern literals are definitions rather than embedded credentials.
        if path.name=="build_release.py":continue
        for pattern,note in patterns:
            if re.search(pattern,text):problems.append(str(path.relative_to(ROOT))+": "+note)
    return problems


def main():
    files=source_files()
    problems=audit(files)
    if problems:raise SystemExit("\n".join(problems))
    dist=ROOT/"dist";dist.mkdir(exist_ok=True)
    from lumen import __version__
    archive=dist/("LUMEN-Science-"+__version__+"-source.zip")
    manifest=[]
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as output:
        for path in files:
            relative=path.relative_to(ROOT).as_posix()
            raw=path.read_bytes()
            manifest.append({"path":relative,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
            output.writestr("LUMEN-Science/"+relative,raw)
        output.writestr("LUMEN-Science/SOURCE_MANIFEST.json",
                        json.dumps(manifest,ensure_ascii=False,indent=2))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist/(archive.name+".sha256")).write_text(digest+"  "+archive.name+"\n",encoding="utf-8")
    print(json.dumps({"archive":str(archive),"files":len(files),"bytes":archive.stat().st_size,
                      "sha256":digest,"source_audit":"passed"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
