#!/usr/bin/env python3
"""Resolve main once: all native jobs consume the same reference-suite revision."""
import functools
import json
import os
import subprocess
import re
from pathlib import Path

@functools.lru_cache(None)
def revision(repo):
    result = subprocess.check_output(['git', 'ls-remote', 'https://github.com/lmctl-ai/'+repo, 'refs/heads/main'], text=True)
    sha = result.split()[0]
    if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid main revision for '+repo)
    return sha

def compiler_version():
    selector = os.environ.get('COMPILER_VERSION') or (Path(__file__).parent/'compiler-version').read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]*', selector):
        raise ValueError('Compiler selector must be a version or npm tag')
    value = json.loads(subprocess.check_output(['npm','view','@lmctl-ai/lmctl@'+selector,'version','--json'],text=True))
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?',value):
        raise ValueError('Compiler selector must resolve to one published version')
    return value

def main():
    platforms = [('ubuntu-24.04','linux-x64'), ('ubuntu-24.04-arm','linux-arm64'), ('macos-26','macos-arm64'), ('macos-26-intel','macos-x64'), ('windows-2022','windows-x64')]
    rows = []
    for language in ['cpp','rust','go','java','csharp','js']:
        runtime = revision('lmcode-'+language)
        # JavaScript's teaching host lives in the runtime repository.
        sample = runtime if language == 'js' else revision('lmcode-'+language+'-sample')
        rows.extend(dict(language=language,os=os_name,platform=platform,runtime_sha=runtime,sample_sha=sample) for os_name,platform in platforms)
    outputs = dict(matrix=json.dumps({'include':rows},separators=(',',':')), reference_sha=revision('lmcode-cpp'), compiler_version=compiler_version())
    for key,value in outputs.items():
        print(key+'='+value)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:
            for key,value in outputs.items(): output.write(key+'='+value+'\n')

if __name__ == '__main__': main()
