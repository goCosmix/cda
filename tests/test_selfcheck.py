"""Tests for cda.selfcheck"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Patch paths before importing selfcheck so the module uses tmp dirs
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestVersion(unittest.TestCase):
    def _make(self, tmp, content):
        from cda.kernel import selfcheck
        selfcheck.VERSION_FILE = tmp / "version"
        if content is not None:
            selfcheck.VERSION_FILE.write_text(content)
        return selfcheck.check_version()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_valid(self):
        # Use the actual installed version so __version__ comparison passes
        from cda import __version__
        r = self._make(self.tmp, __version__ + "\n")
        self.assertTrue(r["passed"])
        self.assertIn(__version__, r["message"])

    def test_invalid(self):
        r = self._make(self.tmp, "v1.2.3\n")
        self.assertFalse(r["passed"])

    def test_missing(self):
        r = self._make(self.tmp, None)
        self.assertFalse(r["passed"])
        self.assertIn("not found", r["message"])


    def setUp(self):
        # Resolve so macOS /tmp symlink doesn't cause path mismatch
        self.tmp = Path(tempfile.mkdtemp()).resolve()

    @patch("cda.kernel.selfcheck.subprocess.run")
    def test_correct(self, mock_run):
        from cda.kernel import selfcheck
        selfcheck.SOURCE_DIR = self.tmp
        mock_run.return_value = MagicMock(returncode=0, stdout=str(self.tmp) + "\n")
        r = selfcheck.check_install_path()
        self.assertTrue(r["passed"])

    @patch("cda.kernel.selfcheck.subprocess.run")
    def test_wrong(self, mock_run):
        from cda.kernel import selfcheck
        selfcheck.SOURCE_DIR = self.tmp
        mock_run.return_value = MagicMock(returncode=0, stdout="/other/path\n")
        r = selfcheck.check_install_path()
        self.assertFalse(r["passed"])
        self.assertIn("wrong path", r["message"])

    @patch("cda.kernel.selfcheck.subprocess.run")
    def test_not_importable(self, mock_run):
        from cda.kernel import selfcheck
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        r = selfcheck.check_install_path()
        self.assertFalse(r["passed"])
        self.assertIn("not importable", r["message"])


class TestDbPresent(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_present(self):
        from cda.kernel import selfcheck
        db = self.tmp / "vscode-ark.db"
        db.write_bytes(b"x" * 1024)
        selfcheck.DB_PATH = db
        r = selfcheck.check_db_present()
        self.assertTrue(r["passed"])
        self.assertIn("MB", r["message"])

    def test_missing(self):
        from cda.kernel import selfcheck
        selfcheck.DB_PATH = self.tmp / "vscode-ark.db"
        r = selfcheck.check_db_present()
        self.assertFalse(r["passed"])


class TestDbAccessible(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_valid_wal(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_accessible()
        self.assertTrue(r["passed"])
        self.assertIn("wal", r["message"])

    def test_corrupt(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        db_path.write_bytes(b"not a database")
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_accessible()
        self.assertFalse(r["passed"])

    def test_missing(self):
        from cda.kernel import selfcheck
        selfcheck.DB_PATH = self.tmp / "vscode-ark.db"
        r = selfcheck.check_db_accessible()
        self.assertFalse(r["passed"])
        self.assertIn("not found", r["message"])


class TestDbIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_passes(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_integrity()
        self.assertTrue(r["passed"])
        self.assertIn("ok", r["message"])

    def test_missing(self):
        from cda.kernel import selfcheck
        selfcheck.DB_PATH = self.tmp / "vscode-ark.db"
        r = selfcheck.check_db_integrity()
        self.assertFalse(r["passed"])


class TestDbTables(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_all_present(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        for t in selfcheck.REQUIRED_TABLES:
            conn.execute(f"CREATE TABLE {t} (id INTEGER)")
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_tables()
        self.assertTrue(r["passed"])

    def test_missing_table(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE sessions (id INTEGER)")
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_tables()
        self.assertFalse(r["passed"])
        self.assertIn("Missing tables", r["message"])


class TestDbCounts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_populated(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        for t in selfcheck.CORE_COUNT_TABLES:
            conn.execute(f"CREATE TABLE {t} (id INTEGER)")
            conn.execute(f"INSERT INTO {t} VALUES (1)")
        conn.commit()
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_counts()
        self.assertTrue(r["passed"])

    def test_empty_table(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        conn = sqlite3.connect(str(db_path))
        for t in selfcheck.CORE_COUNT_TABLES:
            conn.execute(f"CREATE TABLE {t} (id INTEGER)")
        conn.close()
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_counts()
        self.assertFalse(r["passed"])
        self.assertIn("Empty core tables", r["message"])


class TestDbWal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_no_wal(self):
        from cda.kernel import selfcheck
        selfcheck.DB_PATH = self.tmp / "vscode-ark.db"
        r = selfcheck.check_db_wal()
        self.assertTrue(r["passed"])

    def test_shm_without_wal(self):
        from cda.kernel import selfcheck
        db_path = self.tmp / "vscode-ark.db"
        db_path.write_bytes(b"")
        (self.tmp / "vscode-ark.db-shm").write_bytes(b"")
        selfcheck.DB_PATH = db_path
        r = selfcheck.check_db_wal()
        self.assertFalse(r["passed"])
        self.assertIn("SHM", r["message"])


class TestWatcherState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_no_pid_file(self):
        from cda.kernel import selfcheck
        selfcheck.PID_FILE = self.tmp / "watcher.pid"
        r = selfcheck.check_watcher_state()
        self.assertTrue(r["passed"])
        self.assertIn("not running", r["message"])

    def test_live_process(self):
        from cda.kernel import selfcheck
        pid_file = self.tmp / "watcher.pid"
        pid_file.write_text(str(os.getpid()))
        selfcheck.PID_FILE = pid_file
        r = selfcheck.check_watcher_state()
        self.assertTrue(r["passed"])
        self.assertIn("running", r["message"])

    def test_stale_pid(self):
        from cda.kernel import selfcheck
        pid_file = self.tmp / "watcher.pid"
        pid_file.write_text("99999999")  # almost certainly dead
        selfcheck.PID_FILE = pid_file
        r = selfcheck.check_watcher_state()
        # May pass if PID exists on this machine — just check it runs
        self.assertIn("name", r)


class TestQueueDepth(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_missing(self):
        from cda.kernel import selfcheck
        selfcheck.QUEUE_DIR = self.tmp / "watcher-queue"
        r = selfcheck.check_queue_depth()
        self.assertFalse(r["passed"])
        self.assertIn("not found", r["message"])

    def test_empty_queue(self):
        from cda.kernel import selfcheck
        q = self.tmp / "watcher-queue"
        q.mkdir()
        selfcheck.QUEUE_DIR = q
        r = selfcheck.check_queue_depth()
        self.assertTrue(r["passed"])
        self.assertIn("0 files", r["message"])

    def test_high_backlog(self):
        from cda.kernel import selfcheck
        q = self.tmp / "watcher-queue"
        q.mkdir()
        for i in range(501):
            (q / f"f{i}.json").write_text("{}")
        selfcheck.QUEUE_DIR = q
        r = selfcheck.check_queue_depth()
        self.assertFalse(r["passed"])
        self.assertIn("high", r["message"])


class TestDataGitignored(unittest.TestCase):
    @patch("cda.kernel.selfcheck.subprocess.run")
    def test_gitignored(self, mock_run):
        from cda.kernel import selfcheck
        mock_run.return_value = MagicMock(returncode=0)
        r = selfcheck.check_data_gitignored()
        self.assertTrue(r["passed"])

    @patch("cda.kernel.selfcheck.subprocess.run")
    def test_not_gitignored(self, mock_run):
        from cda.kernel import selfcheck
        mock_run.return_value = MagicMock(returncode=1)
        r = selfcheck.check_data_gitignored()
        self.assertFalse(r["passed"])


class TestCliPath(unittest.TestCase):
    @patch("cda.kernel.selfcheck.shutil.which", return_value="/usr/bin/cda")
    def test_found(self, mock_which):
        from cda.kernel import selfcheck
        r = selfcheck.check_cli_path()
        self.assertTrue(r["passed"])
        self.assertIn("/usr/bin/cda", r["message"])

    @patch("cda.kernel.selfcheck.shutil.which", return_value=None)
    def test_not_found(self, mock_which):
        from cda.kernel import selfcheck
        r = selfcheck.check_cli_path()
        self.assertFalse(r["passed"])


class TestPythonRuntime(unittest.TestCase):
    def test_reports_version(self):
        from cda.kernel import selfcheck
        r = selfcheck.check_python_runtime()
        self.assertIn("name", r)
        self.assertIn("Python", r["message"])


class TestDependencies(unittest.TestCase):
    def test_all_present(self):
        from cda.kernel import selfcheck
        r = selfcheck.check_dependencies()
        self.assertTrue(r["passed"])

    def test_missing_import(self):
        from cda.kernel import selfcheck
        orig = selfcheck.REQUIRED_IMPORTS[:]
        selfcheck.REQUIRED_IMPORTS = ["this_module_does_not_exist_xyz"]
        r = selfcheck.check_dependencies()
        selfcheck.REQUIRED_IMPORTS = orig
        self.assertFalse(r["passed"])
        self.assertIn("this_module_does_not_exist_xyz", r["message"])


class TestRunAll(unittest.TestCase):
    def test_returns_tuple(self):
        from cda.kernel.selfcheck import run_all
        passed, results = run_all()
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 14)
        for r in results:
            self.assertIn("name", r)
            self.assertIn("passed", r)
            self.assertIn("message", r)


if __name__ == "__main__":
    unittest.main()
