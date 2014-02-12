"""quixote.ptl_import
$HeadURL: svn+ssh://svn/repos/trunk/quixote/ptl_import.py $
$Id$

Import hooks; when installed, these hooks allow importing .ptl files
as if they were Python modules.

Note: there's some unpleasant incompatibility between ZODB's import
trickery and the import hooks here.  Bottom line: if you're using ZODB,
import it *before* installing the Quixote/PTL import hooks.
"""

__revision__ = "$Id$"


import sys
import os.path
import imp, ihooks, new
import marshal
import stat
import fcntl
import errno
import __builtin__

from ptl_compile import compile_template, PTL_EXT, PTLC_EXT, PTLC_MAGIC

assert sys.hexversion >= 0x20000b1, "need Python 2.0b1 or later"

def _exec_module_code(code, name, filename):
    if sys.modules.has_key(name):
        mod = sys.modules[name] # necessary for reload()
    else:
        mod = new.module(name)
        sys.modules[name] = mod
    mod.__name__ = name
    mod.__file__ = filename
    exec code in mod.__dict__
    return mod

def _load_ptlc(name, filename, file=None):
    if not file:
        try:
            file = open(filename, "rb")
        except IOError:
            return None
    path, ext = os.path.splitext(filename)
    ptl_filename = path + PTL_EXT
    magic = file.read(len(PTLC_MAGIC))
    if magic != PTLC_MAGIC:
        return _load_ptl(name, ptl_filename)
    ptlc_mtime = marshal.load(file)
    try:
        mtime = os.stat(ptl_filename)[stat.ST_MTIME]
    except OSError:
        mtime = ptlc_mtime
    if mtime > ptlc_mtime:
        return _load_ptl(name, ptl_filename)
    code = marshal.load(file)
    return _exec_module_code(code, name, filename)

def _load_ptl(name, filename, file=None):
    if not file:
        try:
            file = open(filename, "rb")
        except IOError:
            return None
    path, ext = os.path.splitext(filename)
    ptlc_filename = path + PTLC_EXT
    try:
        output_fd = os.open(ptlc_filename, os.O_WRONLY | os.O_CREAT, 0644)
        try:
            fcntl.flock(output_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, e:
            if e.errno == errno.EWOULDBLOCK:
                fcntl.flock(output_fd, fcntl.LOCK_EX)
                os.close(output_fd)
                return _load_ptlc(name, ptlc_filename)
            raise
        output = os.fdopen(output_fd, 'wb')
    except (OSError, IOError), e:
        output = None
    try:
        code = compile_template(file, filename, output)
    except:
        # don't leave a corrupt .ptlc file around
        if output:
            output.close()
            os.unlink(ptlc_filename)
        raise
    else:
        if output:
            output.close()
    return _exec_module_code(code, name, filename)


# Constant used to signal a PTL files
PTLC_FILE = 128
PTL_FILE = 129

class PTLHooks(ihooks.Hooks):

    def get_suffixes(self):
        # add our suffixes
        L = imp.get_suffixes()
        return L + [(PTLC_EXT, 'rb', PTLC_FILE), (PTL_EXT, 'r', PTL_FILE)]

class PTLLoader(ihooks.ModuleLoader):

    def load_module(self, name, stuff):
        file, filename, info = stuff
        (suff, mode, type) = info

        # If it's a PTL file, load it specially.
        if type == PTLC_FILE:
            return _load_ptlc(name, filename, file)

        elif type == PTL_FILE:
            return _load_ptl(name, filename, file)

        else:
            # Otherwise, use the default handler for loading
            return ihooks.ModuleLoader.load_module( self, name, stuff)

try:
    import cimport
except ImportError:
    cimport = None

class cModuleImporter(ihooks.ModuleImporter):
    def __init__(self, loader=None):
        self.loader = loader or ihooks.ModuleLoader()
        cimport.set_loader(self.find_import_module)

    def find_import_module(self, fullname, subname, path):
        stuff = self.loader.find_module(subname, path)
        if not stuff:
            return None
        return self.loader.load_module(fullname, stuff)

    def install(self):
        self.save_import_module = __builtin__.__import__
        self.save_reload = __builtin__.reload
        if not hasattr(__builtin__, 'unload'):
            __builtin__.unload = None
        self.save_unload = __builtin__.unload
        __builtin__.__import__ = cimport.import_module
        __builtin__.reload = cimport.reload_module
        __builtin__.unload = self.unload

_installed = 0

def install():
    global _installed
    if not _installed:
        hooks = PTLHooks()
        loader = PTLLoader(hooks)
        if cimport is not None:
            importer = cModuleImporter(loader)
        else:
            importer = ihooks.ModuleImporter(loader)
        ihooks.install(importer)
        _installed = 1


if __name__ == '__main__':
    import ZODB
    install()
