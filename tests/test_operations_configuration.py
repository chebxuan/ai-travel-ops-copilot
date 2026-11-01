"""Offline setup preserves existing secrets and never needs database/network/service access."""
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('configure_operations',Path(__file__).resolve().parents[1]/'scripts/configure_operations.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class ConfigurationTests(unittest.TestCase):
    def test_production_incremental_setup_preserves_existing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'deploy/.env.production';path.parent.mkdir()
            original='API_KEY=original-api\nDB_ADMIN_PASSWORD=original-owner\nDB_READER_PASSWORD=original-reader\nDB_INTAKE_PASSWORD=original-intake\nSITE_ORIGIN=https://example.invalid\n'
            path.write_text(original)
            with patch.object(setup,'ROOT',root),patch('sys.argv',['configure_operations','--target','production']),patch('builtins.input',return_value='operator'),patch.object(setup.getpass,'getpass',return_value='example-password-123'):
                setup.main()
            _,config=setup.read(path)
            self.assertEqual(config['DB_ADMIN_PASSWORD'],'original-owner');self.assertEqual(config['API_KEY'],'original-api')
            self.assertEqual(config['FEISHU_NOTIFICATIONS_ENABLED'],'0')
            self.assertNotEqual(config['OPS_SESSION_KEY'],config['OPS_BACKEND_KEY'])
            self.assertEqual(len(config['DB_OPS_PASSWORD']),64)
            backups=list(path.parent.glob('.env.production.ops-backup-*'))
            self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(),original)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_local_setup_keeps_custom_port_and_synchronizes_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'frontend').mkdir()
            (root/'.env').write_text('API_KEY=local-api\nFEISHU_NOTIFICATIONS_ENABLED=0\n')
            (root/'frontend/.env.local').write_text('BACKEND_BASE_URL=http://127.0.0.1:8008\nBACKEND_API_KEY=existing-key\nSITE_ORIGIN=http://localhost:3001\n')
            with patch.object(setup,'ROOT',root),patch('sys.argv',['configure_operations','--target','local']),patch('builtins.input',return_value='operator'),patch.object(setup.getpass,'getpass',return_value='example-password-123'):
                setup.main()
            _,backend=setup.read(root/'.env');_,frontend=setup.read(root/'frontend/.env.local')
            self.assertEqual(frontend['BACKEND_BASE_URL'],'http://127.0.0.1:8008');self.assertEqual(frontend['BACKEND_API_KEY'],'local-api')
            self.assertEqual(backend['OPS_BACKEND_KEY'],frontend['OPS_BACKEND_KEY'])
            self.assertEqual(backend['OPS_PASSWORD_HASH'],frontend['OPS_PASSWORD_HASH'])

    def test_local_backend_origin_can_replace_stale_port_without_rotating_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'frontend').mkdir()
            (root/'.env').write_text('API_KEY=local-api\n')
            (root/'frontend/.env.local').write_text('BACKEND_BASE_URL=http://127.0.0.1:8001\nBACKEND_API_KEY=stale-key\n')
            with patch.object(setup,'ROOT',root),patch('sys.argv',['configure_operations','--target','local','--backend-url','http://127.0.0.1:8000']),patch('builtins.input',return_value='operator'),patch.object(setup.getpass,'getpass',return_value='example-password-123'):
                setup.main()
            _,backend=setup.read(root/'.env');_,frontend=setup.read(root/'frontend/.env.local')
            self.assertEqual(backend['API_KEY'],'local-api')
            self.assertEqual(frontend['BACKEND_API_KEY'],'local-api')
            self.assertEqual(frontend['BACKEND_BASE_URL'],'http://127.0.0.1:8000')
