from __future__ import annotations

import argparse
import shutil
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_SRC = ROOT / "medical-insurance-system-backend" / "medical_audit_project"
FRONTEND_SRC = ROOT / "medical-insurance-system-front" / "vue-vben-admin" / "apps" / "web-ele" / "src"
OUT_ROOT = ROOT / "audit_package"

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "migrations",
    "tests",
    "test",
    "node_modules",
    "dist",
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "site-packages",
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".css", ".scss", ".less", ".log", ".bak", ".old", ".tmp"}


def should_skip(path: Path) -> bool:
    # Callers pass a source-relative path: rglob does not prune excluded parents.
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    if path.name == "tests.py" or path.name.startswith("test_") or ".test." in path.name or ".spec." in path.name:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    if path.name.endswith(" old.py"):
        return True
    return False


def copy_backend() -> None:
    dst_root = OUT_ROOT / "backend"
    for src in [BACKEND_SRC / "manage.py", BACKEND_SRC / "requirements.txt"]:
        if src.exists():
            dst = dst_root / src.relative_to(BACKEND_SRC)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for path in BACKEND_SRC.rglob("*.py"):
        rel = path.relative_to(BACKEND_SRC)
        if should_skip(rel):
            continue
        if rel.parts[0] in {"media", "mock_patient_data", "scripts"}:
            continue
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def copy_frontend() -> None:
    dst_root = OUT_ROOT / "frontend"
    for path in FRONTEND_SRC.rglob("*"):
        rel = path.relative_to(FRONTEND_SRC)
        if path.is_dir() or should_skip(rel):
            continue
        if path.suffix not in {".vue", ".ts", ".js"}:
            continue
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def make_archive(kind: str) -> Path:
    archive_base = ROOT / "audit_package"
    if kind == "zip":
        out = ROOT / "audit_package.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in OUT_ROOT.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(ROOT))
        return out

    out = ROOT / "audit_package.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.add(OUT_ROOT, arcname=archive_base.name)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", choices=["none", "zip", "tar"], default="zip")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean and OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    copy_backend()
    copy_frontend()

    if args.archive != "none":
        archive = make_archive(args.archive)
        print(archive)
    else:
        print(OUT_ROOT)


if __name__ == "__main__":
    main()
