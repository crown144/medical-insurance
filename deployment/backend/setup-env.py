#!/usr/bin/env python3
"""Merge only the supplied portal keys; never access a database or print secrets."""
import os
from pathlib import Path
import re
import json
import tempfile


ASSIGNMENT = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=')


def merge(original, overlay):
    updates = {}
    for line in overlay.splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            updates[match.group(1)] = line
    result, seen = [], set()
    for line in original.splitlines(keepends=True):
        match = ASSIGNMENT.match(line)
        key = match.group(1) if match else None
        if key in updates:
            if key not in seen:
                result.append(updates[key] + '\n')
                seen.add(key)
        else:
            result.append(line)
    text = ''.join(result)
    if text and not text.endswith('\n'):
        text += '\n'
    for key, line in updates.items():
        if key not in seen:
            text += line + '\n'
    return text


def main():
    metadata = json.loads(Path(__file__).resolve().with_name('DEPLOY_VERSION.json').read_text())
    version = metadata['commit'][:7]
    if not re.fullmatch(r'[0-9a-f]{7}', version):
        raise SystemExit('Invalid release metadata')
    target = Path('.env')
    if not target.is_file() or target.is_symlink():
        raise SystemExit('Run in the existing backend deployment directory; .env must be a regular file.')
    overlay = Path(__file__).resolve().with_name('portal-302.env').read_text()
    original = target.read_text()
    revised = merge(original, overlay)
    backup = target.with_name(f'.env.before-{version}')
    try:
        backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(backup_fd, 'w') as output:
            output.write(original)
    except FileExistsError:
        print(f'Existing backup retained: .env.before-{version}')
    if revised != original:
        fd, name = tempfile.mkstemp(prefix=f'.env-{version}-', dir=str(target.parent))
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(revised)
            os.chmod(name, 0o600)
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    print('Portal configuration merged. Existing app ID, keys and database settings retained.')
    print('No database connections, migrations or account creation were performed.')
    print('Required: retain DJANGO_SECRET_KEY and the registered PORTAL_APP_ID.')
    print('Rule import also requires the existing RULE_IMPORT_LLM_API_KEY.')


if __name__ == '__main__':
    main()
