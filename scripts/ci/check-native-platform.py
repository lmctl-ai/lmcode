#!/usr/bin/env python3
"""Refuse a matrix platform claim that disagrees with the actual native runner."""
import platform
import sys


def native_platform(system=None, machine=None):
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    os_name = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(system)
    architecture = {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(machine.lower())
    if not os_name or not architecture:
        raise ValueError('unsupported native platform: '+system+'/'+machine)
    return os_name+'-'+architecture


if __name__ == '__main__':
    actual = native_platform()
    if len(sys.argv) != 2 or sys.argv[1] != actual:
        raise SystemExit('native platform mismatch: expected '+repr(sys.argv[1:])+', actual '+actual)
    print('PASS native runner '+actual)
