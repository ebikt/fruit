#!/usr/bin/env python
# Coding: Both python2.7 and python3 should execute this code correctly

"""
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-platform-mgt-fru-info-storage-def-v1-0-rev-1-3-spec-update.pdf
https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.0.0.pdf
"""

import os, sys, yaml
import fruit
MYPY = False
if MYPY:
    from typing import Tuple

def error(msg): # type: (str) -> None
    sys.stderr.write("Err: %s\n" % (msg,))
    sys.exit(1)

def process_data(data_in): # type: (bytes) -> Tuple[bytes, bool] # {{{
    firstbyte = bytearray(data_in[0:1])
    if len(firstbyte) == 0:
        error("empty input")
    if firstbyte[0] == 1:
        cfg       = fruit.decode(data_in)
        data_out  = yaml.dump(cfg).encode('utf-8')
        is_binary = False
    else:
        cfg       = yaml.load(data_in) # type: ignore
        data_out  = fruit.encode(cfg)
        is_binary = True
    return data_out, is_binary
# }}}

def read_input(): # {{{
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data_in = f.read()
    else:
        try:
            data_in = sys.stdin.buffer.read()
        except AttributeError:
            data_in = sys.stdin.read()
    return data_in
# }}}

def write_output(data_out, is_binary): # {{{
    if len(sys.argv) > 2:
        with open(sys.argv[2], "wb") as f:
            f.write(data_out)
    elif is_binary and sys.stdout.isatty():
        error("Stdout is terminal, refusing to print binary file")
    else:
        try:
            sys.stdout.buffer.write(data_out)
        except AttributeError:
            sys.stdout.write(data_out)
# }}}

data_in = read_input()
data_out, is_binary = process_data(data_in)
write_output(data_out, is_binary)
