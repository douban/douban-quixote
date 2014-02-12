"""quixote
$HeadURL: svn+ssh://svn/repos/trunk/quixote/__init__.py $
$Id$

A highly Pythonic web application framework.
"""

__revision__ = "$Id$"

__version__ = "1.2"

__all__ = ['Publisher',
           'get_publisher', 'get_request', 'get_session', 'get_user',
           'get_path', 'enable_ptl', 'redirect']


# These are frequently needed by Quixote applications, so make them easy
# to get at.
from quixote.publish import Publisher, \
     get_publisher, get_request, get_path, redirect, \
     get_session, get_session_manager, get_user

# Can't think of anywhere better to put this, so here it is.
def enable_ptl():
    """
    Installs the import hooks needed to import PTL modules.  This must
    be done explicitly because not all Quixote applications need to use
    PTL, and import hooks are deep magic that can cause all sorts of
    mischief and deeply confuse innocent bystanders.  Thus, we avoid
    invoking them behind the programmer's back.  One known problem is
    that, if you use ZODB, you must import ZODB before calling this
    function.
    """
    from quixote import ptl_import
    ptl_import.install()
