import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT/'scripts/ci/check-native-platform.py'
spec = importlib.util.spec_from_file_location('native_platform', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class NativePlatform(unittest.TestCase):
    def test_native_os_and_architecture_aliases(self):
        for system, machine, expected in [('Darwin','arm64','macos-arm64'),('Darwin','x86_64','macos-x64'),('Linux','aarch64','linux-arm64'),('Linux','x86_64','linux-x64'),('Windows','AMD64','windows-x64')]:
            with self.subTest(system=system, machine=machine):
                self.assertEqual(module.native_platform(system,machine), expected)
    def test_unknown_architecture_never_claims_a_known_cell(self):
        with self.assertRaises(ValueError): module.native_platform('Darwin','unknown')
    def test_real_cli_rejects_a_deliberately_wrong_platform(self):
        good = module.native_platform()
        wrong = 'windows-x64' if good != 'windows-x64' else 'linux-arm64'
        result = subprocess.run([sys.executable,str(SCRIPT),wrong],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('native platform mismatch',result.stderr)
