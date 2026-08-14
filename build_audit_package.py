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
BACKEND_KEEP_NAMES = {
    "manage.py",
    "settings.py",
    "urls.py",
    "asgi.py",
    "wsgi.py",
    "celery.py",
    "views.py",
    "models.py",
    "serializers.py",
    "admin.py",
    "forms.py",
    "filters.py",
    "middleware.py",
    "decorators.py",
    "services.py",
    "handlers.py",
    "tasks.py",
    "utils.py",
    "common.py",
    "constants.py",
    "enums.py",
    "exceptions.py",
    "auth.py",
    "apps.py",
    "medical_configs.py",
    "medical_api.py",
    "source_db.py",
    "llm_extractors.py",
    "sl.py",
    "sy.py",
    "config.py",
    "core.py",
    "engine.py",
    "business.py",
    "atomic.py",
    "template_executor.py",
    "rule_executor.py",
    "function_registry.py",
    "llm_api.py",
    "duplicate_billing.py",
    "over_standard.py",
    "over_standard_v2.py",
    "order_charge_evidence.py",
    "father_child_detector.py",
    "package_detector.py",
    "report_generator.py",
    "word_generator.py",
    "predefined_functions.py",
    "example_rules.py",
}


def should_skip(path: Path) -> bool:
    if path.is_dir():
        return path.name in EXCLUDE_DIR_NAMES
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
        if should_skip(path):
            continue
        rel = path.relative_to(BACKEND_SRC)
        if rel.parts[0] in {"media", "mock_patient_data", "scripts"}:
            continue
        if path.name not in BACKEND_KEEP_NAMES and "management" not in rel.parts and len(rel.parts) > 2:
            continue
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def copy_frontend() -> None:
    dst_root = OUT_ROOT / "frontend"
    for path in FRONTEND_SRC.rglob("*"):
        if path.is_dir() or should_skip(path):
            continue
        if path.suffix not in {".vue", ".ts", ".js"}:
            continue
        rel = path.relative_to(FRONTEND_SRC)
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
