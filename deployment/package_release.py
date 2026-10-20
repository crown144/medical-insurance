#!/usr/bin/env python3
"""Package one clean Git commit for the existing offline Docker deployment."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = 'medical-insurance-system-backend/medical_audit_project/'
FRONTEND = 'medical-insurance-system-front/vue-vben-admin/'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob(path):
    return git('show', f'HEAD:{path}')


def add(tar, name, data, executable=False):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o755 if executable else 0o644
    tar.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frontend-dist', type=Path,
                        default=ROOT / FRONTEND / 'apps/web-ele/dist')
    args = parser.parse_args()
    if git('status', '--porcelain').strip():
        raise SystemExit('Commit source changes before packaging a release.')
    commit = git('rev-parse', 'HEAD').decode().strip()
    version = commit[:7]
    dist = args.frontend_dist.resolve()
    html = (dist / 'index.html').read_text()
    if '/yibao/jse/' not in html or re.search(r'<script(?![^>]*\bsrc=)[^>]*>', html):
        raise SystemExit('Build web-ele with build:portal and inline startup loading disabled.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ['backend-latest.tar.gz', 'frontend-latest.tar.gz']):
        raise SystemExit('Release archives already exist; use a new output directory.')
    metadata = json.dumps({
        'branch': 'zzttest', 'commit': commit,
        'backend_source_tree': git('rev-parse', f'HEAD:{BACKEND.rstrip("/")}').decode().strip(),
        'frontend_source_tree': git('rev-parse', f'HEAD:{FRONTEND.rstrip("/")}').decode().strip(),
        'frontend_directory': f'dist-{version}',
        'frontend_build_mode': 'portal', 'frontend_base': '/yibao/',
        'frontend_api_gateway': '/yibao-api',
        'database_migrations': False,
        'portal_mode': 'existing', 'portal_auto_create_users': True,
    }, ensure_ascii=False, indent=2).encode() + b'\n'
    instructions = blob('deployment/README.md').replace(b'RELEASE_COMMIT7', version.encode())
    (output / 'DEPLOY_VERSION.json').write_bytes(metadata)
    (output / '使用说明.md').write_bytes(instructions)

    excluded_dirs = {'media', 'staticfiles', 'uploads', 'feijian_imports', 'logs', '__pycache__'}
    excluded_names = {'.env', 'deploy_settings.py', 'local_settings.py', 'medical_insurance',
                      'db.sqlite3', 'mock_patient_data.zip', 'services.zip', '报错.txt'}
    with tarfile.open(output / 'backend-latest.tar.gz', 'w:gz') as tar:
        for record in git('ls-files', '--stage', '-z', '--', BACKEND).split(b'\0'):
            if not record:
                continue
            attrs, path_bytes = record.split(b'\t', 1)
            path = path_bytes.decode()
            rel = Path(path[len(BACKEND):])
            if (set(rel.parts) & excluded_dirs or rel.name in excluded_names
                    or rel.suffix in {'.pyc', '.pyo', '.log', '.sqlite3'}):
                continue
            add(tar, f'medical_audit_project/{rel}', blob(path), attrs.startswith(b'100755'))
        for name in ['dc', 'setup-env.py', 'compose-no-migrate.yml']:
            add(tar, name, blob(f'deployment/backend/{name}'), name == 'dc')
        add(tar, 'portal-302.env', blob(BACKEND + 'portal_integration/deploy/portal-302.env'))
        add(tar, 'DEPLOY_VERSION.json', metadata)
        add(tar, 'medical_audit_project/DEPLOY_VERSION.json', metadata)
        add(tar, '使用说明.md', instructions)

    with tarfile.open(output / 'frontend-latest.tar.gz', 'w:gz') as tar:
        for path in sorted(dist.rglob('*')):
            if not path.is_file():
                continue
            if path.is_symlink() or path.suffix == '.map' or path.name.startswith('.env'):
                raise SystemExit(f'Unexpected frontend artifact: {path.name}')
            add(tar, f'dist-{version}/{path.relative_to(dist)}', path.read_bytes())
        for name in ['front-sec', 'apply-security.sh']:
            add(tar, name, blob(f'deployment/frontend/{name}'), True)
        prefix = FRONTEND + 'scripts/deploy/security/'
        for path in git('ls-files', '-z', '--', prefix).decode().split('\0'):
            if path:
                add(tar, 'security/' + path[len(prefix):], blob(path))
        add(tar, 'DEPLOY_VERSION.json', metadata)
        add(tar, f'dist-{version}/DEPLOY_VERSION.json', metadata)
        add(tar, '使用说明.md', instructions)

    checksums = []
    for name in ['backend-latest.tar.gz', 'frontend-latest.tar.gz', '使用说明.md', 'DEPLOY_VERSION.json']:
        checksum = hashlib.sha256((output / name).read_bytes()).hexdigest()
        checksums.append(f'{checksum}  {name}\n')
    (output / 'SHA256SUMS').write_text(''.join(checksums))
    print(f'Release {version}: {output}')


if __name__ == '__main__':
    main()
