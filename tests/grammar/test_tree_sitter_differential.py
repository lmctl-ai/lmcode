"""The S3 control corrupts a grammar and proves the gate catches its false negative."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "grammar" / "tree_sitter_differential.py"


class DifferentialGateTests(unittest.TestCase):
    def test_rejecting_a_valid_script_in_a_mutated_grammar_fails_the_gate(self):
        required = ("TREE_SITTER", "LMSCRIPT_BIN", "TREE_SITTER_LMSCRIPT_ROOT", "TREE_SITTER_LMCODE_ROOT")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            self.skipTest("S3 control runs in grammar.yml; missing " + ", ".join(missing))
        grammar = Path(os.environ["TREE_SITTER_LMSCRIPT_ROOT"])
        cli = os.environ["TREE_SITTER"]
        with tempfile.TemporaryDirectory(prefix="lmcode-bad-grammar-") as temp:
            temp_root = Path(temp)
            mutated = temp_root / "grammar"
            shutil.copytree(grammar, mutated, ignore=shutil.ignore_patterns(".git", ".build", "node_modules"))
            source = mutated / "grammar.js"
            original = source.read_text()
            anchor = "identifier: $ => /[A-Za-z_][A-Za-z0-9_]*/,"
            self.assertIn(anchor, original, "pinned grammar identifier anchor changed")
            source.write_text(original.replace(anchor, "identifier: $ => /__never_match_lmscript_control__/,", 1))
            generated = subprocess.run([cli, "generate", str(mutated / "grammar.js")], capture_output=True, text=True)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            library = temp_root / "mutated-lmscript.so"
            built = subprocess.run([cli, "build", str(mutated), "--output", str(library)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

            env = dict(os.environ)
            env["TREE_SITTER_LMSCRIPT_ROOT"] = str(mutated)
            env["TREE_SITTER_LMSCRIPT_LIB"] = str(library)
            env["TREE_SITTER_LMCODE_ROOT"] = os.environ["TREE_SITTER_LMCODE_ROOT"]
            result = subprocess.run(["python3", str(SCRIPT), "--fixture-only", "--only", "lmscript", "--min-documents", "1"],
                env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("UNCLASSIFIED DIVERGENCE control-valid.lms: tree-sitter=reject compiler=accept", result.stderr)


if __name__ == "__main__":
    unittest.main()
