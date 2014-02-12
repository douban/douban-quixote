#!/www/python/bin/python

# Demonstrate Quixote session management, along with the application
# code in session.ptl (aka quixote.demo.session).

__revision__ = "$Id: session_demo.cgi 21182 2003-03-17 21:46:52Z gward $"

import os
from stat import ST_MTIME
from time import time
from cPickle import load, dump
from quixote import enable_ptl
from quixote.session import Session, SessionManager
from quixote.publish import SessionPublisher

class DemoSession (Session):
    """
    Session class that tracks the number of requests made within a
    session.
    """

    def __init__ (self, request, id):
        Session.__init__(self, request, id)
        self.num_requests = 0

    def start_request (self, request):

        # This is called from the main object publishing loop whenever
        # we start processing a new request.  Obviously, this is a good
        # place to track the number of requests made.  (If we were
        # interested in the number of *successful* requests made, then
        # we could override finish_request(), which is called by
        # the publisher at the end of each successful request.)

        Session.start_request(self, request)
        self.num_requests += 1

    def has_info (self):

        # Overriding has_info() is essential but non-obvious.  The
        # session manager uses has_info() to know if it should hang on
        # to a session object or not: if a session is "dirty", then it
        # must be saved.  This prevents saving sessions that don't need
        # to be saved, which is especially important as a defensive
        # measure against clients that don't handle cookies: without it,
        # we might create and store a new session object for every
        # request made by such clients.  With has_info(), we create the
        # new session object every time, but throw it away unsaved as
        # soon as the request is complete.
        # 
        # (Of course, if you write your session class such that
        # has_info() always returns true after a request has been
        # processed, you're back to the original problem -- and in fact,
        # this class *has* been written that way, because num_requests
        # is incremented on every request, which makes has_info() return
        # true, which makes SessionManager always store the session
        # object.  In a real application, think carefully before putting
        # data in a session object that causes has_info() to return
        # true.)

        return (self.num_requests > 0) or Session.has_info(self)

    is_dirty = has_info


class DirMapping:
    """A mapping object that stores values as individual pickle
    files all in one directory.  You wouldn't want to use this in
    production unless you're using a filesystem optimized for
    handling large numbers of small files, like ReiserFS.  However,
    it's pretty easy to implement and understand, it doesn't require
    any external libraries, and it's really easy to browse the
    "database".
    """

    def __init__ (self, save_dir=None):
        self.set_save_dir(save_dir)
        self.cache = {}
        self.cache_time = {}

    def set_save_dir (self, save_dir):
        self.save_dir = save_dir
        if save_dir and not os.path.isdir(save_dir):
            os.mkdir(save_dir, 0700)
    
    def keys (self):
        return os.listdir(self.save_dir)

    def values (self):
        # This is pretty expensive!
        return [self[id] for id in self.keys()]

    def items (self):
        return [(id, self[id]) for id in self.keys()]

    def _gen_filename (self, session_id):
        return os.path.join(self.save_dir, session_id)

    def __getitem__ (self, session_id):

        filename = self._gen_filename(session_id)
        if (self.cache.has_key(session_id) and
            os.stat(filename)[ST_MTIME] <= self.cache_time[session_id]):
            return self.cache[session_id]

        if os.path.exists(filename):
            try:
                file = open(filename, "rb")
                try:
                    print "loading session from %r" % file
                    session = load(file)
                    self.cache[session_id] = session
                    self.cache_time[session_id] = time()
                    return session
                finally:
                    file.close()
            except IOError, err:
                raise KeyError(session_id,
                               "error reading session from %s: %s"
                               % (filename, err))
        else:
            raise KeyError(session_id,
                           "no such file %s" % filename)

    def get (self, session_id, default=None):
        try:
            return self[session_id]
        except KeyError:
            return default

    def has_key (self, session_id):
        return os.path.exists(self._gen_filename(session_id))

    def __setitem__ (self, session_id, session):
        filename = self._gen_filename(session.id)
        file = open(filename, "wb")
        print "saving session to %s" % file
        dump(session, file, 1)
        file.close()

        self.cache[session_id] = session
        self.cache_time[session_id] = time()

    def __delitem__ (self, session_id):
        filename = self._gen_filename(session_id)
        if os.path.exists(filename):
            os.remove(filename)
            if self.cache.has_key(session_id):
                del self.cache[session_id]
                del self.cache_time[session_id]
        else:
            raise KeyError(session_id, "no such file: %s" % filename)


# This is mostly the same as the standard boilerplate for any Quixote
# driver script.  The main difference is that we have to instantiate a
# session manager, and use SessionPublisher instead of the normal
# Publisher class.  Just like demo.cgi, we use demo.conf to setup log
# files and ensure that error messages are more informative than secure.

# You can use the 'shelve' module to create an alternative persistent
# mapping to the DirMapping class above.
#import shelve
#sessions = shelve.open("/tmp/quixote-sessions")

enable_ptl()
sessions = DirMapping(save_dir="/tmp/quixote-session-demo")
session_mgr = SessionManager(session_class=DemoSession,
                             session_mapping=sessions)
app = SessionPublisher('quixote.demo.session', session_mgr=session_mgr)
app.read_config("demo.conf")
app.setup_logs()
app.publish_cgi()
