"""quixote.util
$HeadURL: svn+ssh://svn/repos/trunk/quixote/util.py $
$Id$

Contains various useful functions and classes:

  xmlrpc(request, func) : Processes the body of an XML-RPC request, and calls
                          'func' with the method name and parameters.
  StaticFile            : Wraps a file from a filesystem as a
                          Quixote resource.
  StaticDirectory       : Wraps a directory containing static files as
                          a Quixote namespace.

StaticFile and StaticDirectory were contributed by Hamish Lawson.
See doc/static-files.txt for examples of their use.
"""

import sys
import os
import re
import time
import binascii
import mimetypes
import urllib
import xmlrpclib
from cStringIO import StringIO
from rfc822 import formatdate
from quixote import errors, html
from quixote.http_response import Stream

if hasattr(os, 'urandom'):
    # available in Python 2.4 and also works on win32
    def randbytes(bytes):
        """Return bits of random data as a hex string."""
        return binascii.hexlify(os.urandom(bytes))

elif os.path.exists('/dev/urandom'):
    # /dev/urandom is just as good as /dev/random for cookies (assuming
    # SHA-1 is secure) and it never blocks.
    def randbytes(bytes):
        """Return bits of random data as a hex string."""
        return binascii.hexlify(open("/dev/urandom").read(bytes))

else:
    # this is much less secure than the above function
    import sha
    class _PRNG:
        def __init__(self):
            self.state = sha.new(str(time.time() + time.clock()))
            self.count = 0

        def _get_bytes(self):
            self.state.update('%s %d' % (time.time() + time.clock(),
                                         self.count))
            self.count += 1
            return self.state.hexdigest()

        def randbytes(self, bytes):
            """Return bits of random data as a hex string."""
            s = ""
            chars = 2*bytes
            while len(s) < chars:
                s += self._get_bytes()
            return s[:chars]

    randbytes = _PRNG().randbytes


def xmlrpc(request, func):
    """xmlrpc(request:Request, func:callable) : string

    Processes the body of an XML-RPC request, and calls 'func' with
    two arguments, a string containing the method name and a tuple of
    parameters.
    """

    # Get contents of POST body
    if request.get_method() != 'POST':
        request.response.set_status(405, "Only the POST method is accepted")
        return "XML-RPC handlers only accept the POST method."

    length = int(request.environ['CONTENT_LENGTH'])
    data = request.stdin.read(length)

    # Parse arguments
    params, method = xmlrpclib.loads(data)

    try:
        result = func(method, params)
    except xmlrpclib.Fault, exc:
        result = exc
    except:
        # report exception back to client
        result = xmlrpclib.dumps(
            xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type, sys.exc_value))
            )
    else:
        result = (result,)
        result = xmlrpclib.dumps(result, methodresponse=1)

    request.response.set_content_type('text/xml')
    return result


class FileStream(Stream):

    CHUNK_SIZE = 20000

    def __init__(self, fp, size=None):
        self.fp = fp
        self.length = size

    def __iter__(self):
        return self

    def next(self):
        chunk = self.fp.read(self.CHUNK_SIZE)
        if not chunk:
            raise StopIteration
        return chunk


class StaticFile:

    """
    Wrapper for a static file on the filesystem.
    """

    def __init__(self, path, follow_symlinks=0,
                 mime_type=None, encoding=None, cache_time=None):
        """StaticFile(path:string, follow_symlinks:bool)

        Initialize instance with the absolute path to the file.  If
        'follow_symlinks' is true, symbolic links will be followed.
        'mime_type' specifies the MIME type, and 'encoding' the
        encoding; if omitted, the MIME type will be guessed,
        defaulting to text/plain.

        Optional cache_time parameter indicates the number of
        seconds a response is considered to be valid, and will
        be used to set the Expires header in the response when
        quixote gets to that part.  If the value is None then
        the Expires header will not be set.
        """

        # Check that the supplied path is absolute and (if a symbolic link) may
        # be followed
        self.path = path
        if not os.path.isabs(path):
            raise ValueError, "Path %r is not absolute" % path
        if os.path.islink(path) and not follow_symlinks:
            raise errors.TraversalError(private_msg="Path %r is a symlink"
                                        % path)

        # Decide the Content-Type of the file
        guess_mime, guess_enc = mimetypes.guess_type(os.path.basename(path),
                                                     strict=0)
        self.mime_type = mime_type or guess_mime or 'text/plain'
        self.encoding = encoding or guess_enc or None
        self.cache_time = cache_time

    def __call__(self, request):
        stat = os.stat(self.path)
        last_modified = formatdate(stat.st_mtime)
        if last_modified == request.get_header('If-Modified-Since'):
            # handle exact match of If-Modified-Since header
            request.response.set_status(304)
            return ''

        # Set the Content-Type for the response and return the file's contents.
        request.response.set_content_type(self.mime_type)
        if self.encoding:
            request.response.set_header("Content-Encoding", self.encoding)

        request.response.set_header('Last-Modified', last_modified)

        if self.cache_time is None:
            request.response.cache = None # don't set the Expires header
        else:
            # explicitly allow client to cache page by setting the Expires
            # header, this is even more efficient than the using
            # Last-Modified/If-Modified-Since since the browser does not need
            # to contact the server
            request.response.cache = self.cache_time

        return FileStream(open(self.path, 'rb'), stat.st_size)


class StaticDirectory:

    """
    Wrap a filesystem directory containing static files as a Quixote namespace.
    """

    _q_exports = []

    FILE_CLASS = StaticFile

    def __init__(self, path, use_cache=0, list_directory=0, follow_symlinks=0,
                 cache_time=None, file_class=None, index_filenames=None):
        """StaticDirectory(path:string, use_cache:bool, list_directory:bool,
                           follow_symlinks:bool, cache_time:int,
                           file_class=None, index_filenames:[string])

        Initialize instance with the absolute path to the file.
        If 'use_cache' is true, StaticFile instances will be cached in memory.
        If 'list_directory' is true, users can request a directory listing.
        If 'follow_symlinks' is true, symbolic links will be followed.

        Optional parameter cache_time allows setting of Expires header in
        response object (see note for StaticFile for more detail).

        Optional parameter 'index_filenames' specifies a list of
        filenames to be used as index files in the directory. First
        file found searching left to right is returned.
        """

        # Check that the supplied path is absolute
        self.path = path
        if not os.path.isabs(path):
            raise ValueError, "Path %r is not absolute" % path

        self.use_cache = use_cache
        self.cache = {}
        self.list_directory = list_directory
        self.follow_symlinks = follow_symlinks
        self.cache_time = cache_time
        if file_class is not None:
            self.file_class = file_class
        else:
            self.file_class = self.FILE_CLASS
        self.index_filenames = index_filenames

    def _q_index(self, request):
        """
        If directory listings are allowed, generate a simple HTML
        listing of the directory's contents with each item hyperlinked;
        if the item is a subdirectory, place a '/' after it. If not allowed,
        return a page to that effect.
        """
        if self.index_filenames:
            for name in self.index_filenames:
                try:
                    obj = self._q_lookup(request, name)
                except errors.TraversalError:
                    continue
                if not isinstance(obj, StaticDirectory) and callable(obj):
                    return obj(request)
        # FIXME: this is not a valid HTML document!
        out = StringIO()
        if self.list_directory:
            template = html.htmltext('<a href="%s">%s</a>%s')
            print >>out, (html.htmltext("<h1>%s</h1>")
                          % request.environ['REQUEST_URI'])
            print >>out, "<pre>"
            print >>out, template % ('..', '..', '')
            files = os.listdir(self.path)
            files.sort()
            for filename in files:
                filepath = os.path.join(self.path, filename)
                marker = os.path.isdir(filepath) and "/" or ""
                print >>out, \
                        template % (urllib.quote(filename), filename, marker)
            print >>out, "</pre>"
        else:
            print >>out, "<h1>Directory listing denied</h1>"
            print >>out, \
                "<p>This directory does not allow its contents to be listed.</p>"
        return out.getvalue()

    def _q_lookup(self, request, name):
        """
        Get a file from the filesystem directory and return the StaticFile
        or StaticDirectory wrapper of it; use caching if that is in use.
        """
        if name in ('.', '..'):
            raise errors.TraversalError(private_msg="Attempt to use '.', '..'")
        if self.cache.has_key(name):
            # Get item from cache
            item = self.cache[name]
        else:
            # Get item from filesystem; cache it if caching is in use.
            item_filepath = os.path.join(self.path, name)
            while os.path.islink(item_filepath):
                if not self.follow_symlinks:
                    raise errors.TraversalError
                else:
                    dest = os.readlink(item_filepath)
                    item_filepath = os.path.join(self.path, dest)

            if os.path.isdir(item_filepath):
                # avoid passing post 1.0 keyword arguments to subclasses that
                # may not support them
                kwargs = {}
                if self.index_filenames is not None:
                    kwargs['index_filenames'] = self.index_filenames
                item = self.__class__(item_filepath, self.use_cache,
                                      self.list_directory,
                                      self.follow_symlinks, self.cache_time,
                                      self.file_class, **kwargs)
            elif os.path.isfile(item_filepath):
                item = self.file_class(item_filepath, self.follow_symlinks,
                                       cache_time=self.cache_time)
            else:
                raise errors.TraversalError
            if self.use_cache:
                self.cache[name] = item
        return item


class Redirector:
    """
    A simple class that can be used from inside _q_lookup() to redirect
    requests.
    """

    _q_exports = []

    def __init__(self, location, permanent=0):
        self.location = location
        self.permanent = permanent

    def _q_lookup(self, request, component):
        return self

    def __call__(self, request):
        return request.redirect(self.location, self.permanent)

re_xml_illegal = u'[\u000b\u000c\u00a0\u00ad\u0337\u0338\u115f\u1160\u205f\u3164\ufeff\uffa0\u0000-\u0008\u000e-\u001f\u0080-\u009f\u2000-\u200f\u202a-\u202f\u206a-\u206f\ufff9-\ufffb\ufffe-\uffff]'

CONTROL_RE = re.compile(re_xml_illegal)
def filter_input(s):
    """filter all the illegal and a few invisible control char in unicode xml charset.

    def compare_func(s):
        return s.decode('utf8', 'ignore').encode('utf8','ignore')

    speed:
        compare_func:  254,359,978 char/second
        filter_input:   70,416,666 char/second
        test_input: a utf-8 str include bad_unicode char, length 10647
    """
    return CONTROL_RE.sub('',s.decode('utf8', 'ignore')).encode('utf8','ignore')

def convert_unicode_to_utf8_in_json(json):
    def _do_transform(val):
        mapper = {
            unicode: lambda x: x.encode('utf-8'),
            list: lambda x: _transform_list(x),
            dict: lambda x: _transform_dict(x),
        }
        type_ = type(val)

        return mapper[type_](val) if type_ in mapper else val

    def _transform_dict(old_di):
        new_dict = {}
        for old_k, old_v in old_di.iteritems():
            new_k = old_k.encode('utf-8') if type(old_k) is unicode else old_k
            new_dict[new_k] = _do_transform(old_v)
        return new_dict

    def _transform_list(li):
        return [_do_transform(i) for i in li]

    return _do_transform(json)
