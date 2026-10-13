import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_audit_package as builder


class AuditSourcePackageTests(unittest.TestCase):
    def test_backend_keeps_nested_services_and_excludes_non_source_trees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            kept = [
                'portal_integration/services/__init__.py',
                'portal_integration/services/portal_client.py',
                'portal_integration/services/user_sync.py',
                'portal_integration/services/crypto.py',
                'accounts/management/commands/create_developer.py',
            ]
            excluded = [
                '.venv/lib/package/views.py',
                'portal_integration/tests/views.py',
                'accounts/migrations/0001_initial.py',
                'accounts/tests.py',
                'accounts/test_auth.py',
                'media/models.py',
            ]
            for name in kept + excluded:
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('# fixture\n')
            with patch.object(builder, 'BACKEND_SRC', source), patch.object(
                builder, 'OUT_ROOT', root / 'output'
            ):
                builder.copy_backend()
            actual = {
                file.relative_to(root / 'output/backend').as_posix()
                for file in (root / 'output/backend').rglob('*.py')
            }
            self.assertEqual(actual, set(kept))

    def test_frontend_excludes_nested_dependencies_and_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            for name in ['api/auth.ts', 'api/auth.test.ts', 'api/tests/index.ts', 'node_modules/lib/index.js']:
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('// fixture\n')
            with patch.object(builder, 'FRONTEND_SRC', source), patch.object(
                builder, 'OUT_ROOT', root / 'output'
            ):
                builder.copy_frontend()
            actual = {
                file.relative_to(root / 'output/frontend').as_posix()
                for file in (root / 'output/frontend').rglob('*') if file.is_file()
            }
            self.assertEqual(actual, {'api/auth.ts'})


if __name__ == '__main__':
    unittest.main()
