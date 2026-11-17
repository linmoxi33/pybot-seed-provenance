#!/usr/bin/env python3
"""Stub PyBot used by the tests and by examples/out.

Speaks the same surface as `python -m pybot -s N -v`: one reply per input line
on stdout, one `[module: name | N ms]` line per input line on stderr.
STUB_MODE picks which upstream behaviour to emulate.
"""
import os
import sys

mode = os.environ.get("STUB_MODE", "stable")
seed = 0
argv = sys.argv[1:]
if "-s" in argv:
    seed = int(argv[argv.index("-s") + 1])

REPLIES = ["Hi there.", "Hello friend.", "Hey, good to see you."]
MODULES = ["greet", "smalltalk", "memory"]
counter = 0
NONDET_INDEX = 0
if mode == "nondet":
    # Simulates a real bot whose reply depends on more than the seed: a
    # persistent counter that survives the process. Read once per process, so
    # a single run is internally consistent but two runs of one seed differ.
    _path = "/tmp/.pybot-stub-counter"
    try:
        with open(_path) as _handle:
            NONDET_INDEX = int(_handle.read().strip() or 0)
    except (OSError, ValueError):
        NONDET_INDEX = 0
    with open(_path, "w") as _handle:
        _handle.write(str(NONDET_INDEX + 1))

for line in sys.stdin:
    text = line.rstrip("\n")
    if mode == "stable":
        module, reply = "greet", "Hi there."
    elif mode == "wording":
        module, reply = "greet", REPLIES[seed % len(REPLIES)]
    elif mode == "module":
        module, reply = MODULES[seed % len(MODULES)], "Hi there."
    elif mode == "both":
        module = MODULES[seed % len(MODULES)]
        reply = REPLIES[seed % len(REPLIES)]
    elif mode == "fallback":
        module, reply = "greet", "Hello!"
    elif mode == "nondet":
        module, reply = "greet", REPLIES[NONDET_INDEX % len(REPLIES)]
    elif mode == "desync":
        module, reply = "greet", "Hi there."
    else:
        sys.stderr.write("unknown STUB_MODE %s\n" % mode)
        sys.exit(3)
    print(reply, flush=True)
    if mode != "desync":
        print("[module: %s | 3 ms]" % module, file=sys.stderr, flush=True)