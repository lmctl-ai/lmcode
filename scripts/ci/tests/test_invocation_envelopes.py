"""Specification qualification against canonical native bytes, no host fallback."""
import json
import math
from pathlib import Path
import unittest
import re
import tempfile
import shutil
ROOT=Path(__file__).resolve().parents[3]
SAFE=9007199254740991

def integer(value):
    return type(value)in(int,float)and abs(value)<=SAFE and math.isfinite(value)and int(value)==value

def validate(value,case):
    count=len(case['programs']);builder=case['mode']=='builder'or(case['mode']is None and count>1)
    assert isinstance(value,dict)and type(value.get('ok'))is bool
    if value['ok']:
        assert case['exit']==0
        assert set(value)==({'ok','result','parts'}if builder else {'ok','result'})
        if builder:assert integer(value['parts'])and value['parts']==count and isinstance(value['result'],list)and len(value['result'])==count
    else:
        assert {'ok','phase','code','message'}<=set(value)<= {'ok','phase','code','message','line','column','part'}
        assert all(isinstance(value[k],str)for k in ['phase','code','message'])
        assert {'cli':2,'load':3,'run':3,'app':4}.get(value['phase'])==case['exit']
        if 'line'in value:assert integer(value['line'])and value['line']>0
        if 'column'in value:assert 'line'in value and integer(value['column'])and value['column']>0
        if 'part'in value:assert builder and integer(value['part'])and 0<=value['part']<count

def check_boundary_bytes(reference,mirror):
    for name in ['canonical-numbers.expect','canonical-controls.expect','metadata-errors.json']:
        assert (reference/name).read_bytes()==(mirror/name).read_bytes(),('spec/native byte drift',name)

def check_native_goldens(cpp):
    folder=Path(cpp)/'conformance/invocation-vectors';manifest=json.loads((folder/'manifest.json').read_text())
    assert len(manifest['cases'])>=14
    for case in manifest['cases']:
        raw=(folder/(case['name']+'.expect')).read_bytes();lines=raw.decode('utf8').splitlines()
        assert raw.endswith(b'LMCODE_RETURN_END\n')and b'\r'not in raw
        assert(len(lines),lines[0],lines[-1])==(3,'LMCODE_RETURN_BEGIN','LMCODE_RETURN_END')
        validate(json.loads(lines[1]),case)
    mirror=ROOT/'tests/fixtures/invocation-boundaries'
    check_boundary_bytes(folder,mirror)
    return len(manifest['cases'])

class InvocationEnvelopes(unittest.TestCase):
    def test_canonical_boundary_bytes_and_controls(self):
        folder=ROOT/'tests/fixtures/invocation-boundaries'
        numbers=(folder/'canonical-numbers.expect').read_bytes()
        self.assertIn(b'1e-07,5e-324,1e-323',numbers)
        self.assertIn(b'1e+06,999999,1.0000005e+06',numbers)
        controls=(folder/'canonical-controls.expect').read_bytes()
        self.assertIn(b'\\b\\t\\n\\u000b\\f',controls)
        errors=json.loads((folder/'metadata-errors.json').read_text())
        self.assertGreaterEqual(len(errors),24)
        for case in errors:
            value=json.loads(case['frame'].splitlines()[1])
            validate(value,{'mode':'single','programs':['unused'],'exit':2})
            self.assertEqual(case['frame'],'LMCODE_RETURN_BEGIN\n'+json.dumps(value,separators=(',',':'),ensure_ascii=False)+'\nLMCODE_RETURN_END\n')

    def test_exact_byte_oracle_rejects_value_equivalent_encodings(self):
        mirror=ROOT/'tests/fixtures/invocation-boundaries'
        controls=[('canonical-numbers.expect',b'1e-07',b'1.0E-7'),
                  ('canonical-numbers.expect',b'5e-324',b'4.9E-324'),
                  ('canonical-controls.expect',b'\\b',b'\\u0008'),
                  ('metadata-errors.json',b'/parts/0/index',b'')]
        with tempfile.TemporaryDirectory() as temporary:
            copy=Path(temporary)/'fixtures';shutil.copytree(mirror,copy)
            check_boundary_bytes(copy,mirror)
            for name,before,after in controls:
                original=(copy/name).read_bytes();self.assertIn(before,original)
                (copy/name).write_bytes(original.replace(before,after))
                with self.subTest(name=name,before=before),self.assertRaises(AssertionError):
                    check_boundary_bytes(copy,mirror)
                (copy/name).write_bytes(original)

    def test_normative_spec_examples(self):
        text=(ROOT/'spec/host-protocol.md').read_text()
        examples=re.findall(r'```text\nLMCODE_RETURN_BEGIN\n([^\n]+)\nLMCODE_RETURN_END\n```',text)
        self.assertEqual(len(examples),3)
        cases=[{'mode':'single','programs':['a'],'exit':0},{'mode':'builder','programs':['a','b'],'exit':0},{'mode':'builder','programs':['a','b'],'exit':3}]
        for raw,case in zip(examples,cases):validate(json.loads(raw),case)
    def test_wrong_count_partial_payload_and_bare_value_controls(self):
        builder={'mode':'builder','programs':['a'],'exit':0}
        validate({'ok':True,'result':[[1]],'parts':1},builder)
        for value in [{'ok':True,'result':[[1]]},{'ok':True,'result':[[1]],'parts':2},[1]]:
            with self.subTest(value=value),self.assertRaises(AssertionError):validate(value,builder)
        failed={'mode':'builder','programs':['a','b'],'exit':3}
        good={'ok':False,'phase':'run','code':'RUN_HOST','message':'bad','part':0}
        validate(good,failed)
        for change in [{'result':[None]},{'part':2},{'column':1},{'phase':'app'}]:
            value=dict(good,**change)
            with self.subTest(change=change),self.assertRaises(AssertionError):validate(value,failed)
if __name__=='__main__':unittest.main()
