
_q_exports = ["simple", "error", "publish_error", "widgets",
              "form_demo", "dumpreq", "srcdir",
              ("favicon.ico", "q_ico")]

import sys
from quixote.demo.pages import _q_index, _q_exception_handler, dumpreq
from quixote.demo.widgets import widgets
from quixote.demo.integer_ui import IntegerUI
from quixote.errors import PublishError
from quixote.util import StaticDirectory, StaticFile

def simple(request):
    # This function returns a plain text document, not HTML.
    request.response.set_content_type("text/plain")
    return "This is the Python function 'quixote.demo.simple'.\n"

def error(request):
    raise ValueError, "this is a Python exception"

def publish_error(request):
    raise PublishError(public_msg="Publishing error raised by publish_error")

def _q_lookup(request, component):
    return IntegerUI(request, component)

def _q_resolve(component):
    # _q_resolve() is a hook that can be used to import only
    # when it's actually accessed.  This can be used to make
    # start-up of your application faster, because it doesn't have
    # to import every single module when it starts running.
    if component == 'form_demo':
        from quixote.demo.forms import form_demo
        return form_demo

# Get current directory
import os
from quixote.demo import forms
curdir = os.path.dirname(forms.__file__)
srcdir = StaticDirectory(curdir, list_directory=1)
q_ico = StaticFile(os.path.join(curdir, 'q.ico'))
