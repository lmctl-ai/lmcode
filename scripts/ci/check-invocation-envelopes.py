#!/usr/bin/env python3
"""Cross-reference the normative specification with the C++ native goldens."""
import os
from pathlib import Path
import runpy
root=Path(__file__).resolve().parent
check=runpy.run_path(str(root/'tests/test_invocation_envelopes.py'))['check_native_goldens']
print('PASS specification/native envelope parity:',check(os.environ['LMCODE_CPP']),'goldens')
