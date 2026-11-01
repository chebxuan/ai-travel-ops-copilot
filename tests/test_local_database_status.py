"""Status diagnostics without starting or connecting to any database."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch
from scripts.local_database import report_status


class LocalDatabaseStatusTests(unittest.TestCase):
    def check_status(self, code, stdout='', stderr=''):
        output, error = io.StringIO(), io.StringIO()
        result = subprocess.CompletedProcess(['pg_ctl'], code, stdout, stderr)
        with patch('scripts.local_database.subprocess.run', return_value=result) as run, contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            actual = report_status(['pg_ctl', '-D', '/test-data', 'status'])
        run.assert_called_once_with(['pg_ctl', '-D', '/test-data', 'status'], capture_output=True, text=True, check=False)
        self.assertEqual(actual, code)
        self.assertNotIn('Traceback', output.getvalue() + error.getvalue())
        return output.getvalue(), error.getvalue()

    def test_stopped_has_start_hint_and_preserves_exit_code(self):
        output, _ = self.check_status(3, 'pg_ctl: no server running\n')
        self.assertIn('未运行', output)
        self.assertIn('scripts/local_database.py start', output)

    def test_running(self):
        output, _ = self.check_status(0, 'pg_ctl: server is running\n')
        self.assertIn('正在运行', output)
        self.assertNotIn(' start', output)

    def test_unexpected_error_remains_failure(self):
        output, error = self.check_status(1, stderr='Unable to inspect server')
        self.assertIn('无法确认', output)
        self.assertIn('Unable to inspect', error)
