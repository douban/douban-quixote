#! /usr/bin/env python
"""
Dump the information contained in a compiled PTL file.  Based on the
dumppyc.py script in the Tools/compiler directory of the Python
distribution.
"""

__revision__ = "$Id$"

import marshal
import dis
import types

from ptl_compile import PTLC_MAGIC

def dump(obj):
    print obj
    for attr in dir(obj):
        print "\t", attr, repr(getattr(obj, attr))

def loadCode(path):
    f = open(path)
    magic = f.read(len(PTLC_MAGIC))
    if magic != PTLC_MAGIC:
        raise ValueError, 'bad .ptlc magic for file "%s"' % path
    mtime = marshal.load(f)
    co = marshal.load(f)
    f.close()
    return co

def walk(co, match=None):
    if match is None or co.co_name == match:
        dump(co)
        print
        dis.dis(co)
    for obj in co.co_consts:
        if type(obj) == types.CodeType:
            walk(obj, match)

def main(filename, codename=None):
    co = loadCode(filename)
    walk(co, codename)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        filename, codename = sys.argv[1:]
    else:
        filename = sys.argv[1]
        codename = None
    main(filename, codename)
