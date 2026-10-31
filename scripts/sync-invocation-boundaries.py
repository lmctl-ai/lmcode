#!/usr/bin/env python3
"""Mirror the reference's committed JSON boundary bytes for specification checks."""
import argparse,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
cpp=os.environ['LMCODE_CPP'];commit=subprocess.check_output(['git','-C',cpp,'rev-parse','HEAD'],text=True).strip()
folder=root/'tests/fixtures/invocation-boundaries'
for name in ['canonical-numbers.expect','canonical-controls.expect','metadata-errors.json']:
 raw=subprocess.check_output(['git','-C',cpp,'show',commit+':conformance/invocation-vectors/'+name])
 target=folder/name
 if args.check:assert target.read_bytes()==raw,('stale boundary fixture',name)
 else:folder.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
if not args.check:(folder/'SOURCE_COMMIT').write_text(commit+'\n')
print('PASS committed invocation boundary fixture parity')
