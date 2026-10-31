#!/usr/bin/env python3
"""Resolve main once: all native jobs consume the same reference-suite revision."""
import functools
import json
import os
import subprocess

@functools.lru_cache(None)
def revision(repo):
    result = subprocess.check_output(['git', 'ls-remote', 'https://github.com/lmctl-ai/'+repo, 'refs/heads/main'], text=True)
    sha = result.split()[0]
    if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid main revision for '+repo)
    return sha

platforms = [('ubuntu-24.04','linux-x64'), ('ubuntu-24.04-arm','linux-arm64'), ('macos-15','macos-arm64'), ('macos-15-intel','macos-x64'), ('windows-2022','windows-x64')]
rows = []
for language in ['cpp','rust','go','java','csharp']:
    runtime = revision('lmcode-'+language)
    sample = revision('lmcode-'+language+'-sample')
    rows.extend(dict(language=language,os=os_name,platform=platform,runtime_sha=runtime,sample_sha=sample) for os_name,platform in platforms)
outputs = dict(matrix=json.dumps({'include':rows},separators=(',',':')), reference_sha=revision('lmcode-cpp'))
for key,value in outputs.items():
    print(key+'='+value)
if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:
        for key,value in outputs.items(): output.write(key+'='+value+'\n')
