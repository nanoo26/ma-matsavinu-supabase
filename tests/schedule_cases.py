"""Execute only a copied scheduler and fake backup script in temporary folders."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from offline_support import OfflineCase, ROOT


@unittest.skipUnless(os.name == "nt", "Windows batch integration")
class ScheduleCases(OfflineCase):
    def test_scheduler_propagates_success_and_failure(self):
        for code in (0, 7):
            with self.subTest(exit_code=code), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                wrapper = folder / "backup_schedule.bat"
                wrapper.write_bytes((ROOT / "backup_schedule.bat").read_bytes())
                activate = folder / ".venv" / "Scripts" / "activate.bat"
                activate.parent.mkdir(parents=True)
                activate.write_text("@echo off\nexit /b 0\n")
                (folder / "deactivate.bat").write_text("@echo off\nexit /b 0\n")
                (folder / "backup_daily.py").write_text(f"raise SystemExit({code})\n")
                environment = dict(os.environ)
                environment["PATH"] = str(folder) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
                result = subprocess.run(["cmd", "/d", "/c", str(wrapper)], env=environment, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, code, result.stderr.decode(errors="replace"))
                log = (folder / "backup_log.txt").read_text()
                self.assertIn("Backup completed" if code == 0 else "Backup FAILED", log)
                if code:
                    self.assertNotIn("Backup completed", log)
