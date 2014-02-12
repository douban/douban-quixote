"""quixote.upload
$HeadURL: svn+ssh://svn/repos/trunk/quixote/upload.py $
$Id$

Code for handling HTTP upload requests.  Provides HTTPUploadRequest, a
subclass of HTTPRequest that is created when handling an HTTP request
whose Content-Type is "multipart/form-data".  Also provides the Upload
class, which is used as the form value for "file upload" variables.
"""

__revision__ = "$Id$"

import os, string
import errno
from cgi import parse_header
from rfc822 import Message
from time import time, strftime, localtime

from quixote.http_request import HTTPRequest
from quixote.errors import RequestError
from quixote.config import ConfigError

CRLF = "\r\n"
LF = "\n"


def read_mime_part(file, boundary, lines=None, ofile=None):
    """
    Read lines from 'file' up to and including a MIME message boundary
    derived from 'boundary'.  Return true if there is no more data to be
    read from 'file', ie. we hit either a MIME outer boundary or EOF.

    If 'lines' is supplied, each line is stripped of line-endings and
    appended to 'lines'.  If 'ofile' is supplied, each line is written
    to 'ofile' as-is (ie. with line-endings intact).  Neither the
    boundary line nor a blank line preceding it (if any) will be
    saved/written.  If neither 'lines' nor 'ofile' is supplied, the data
    read is discarded.
    """
    # Algorithm based on read_lines_to_outerboundary() in cgi.py

    next = "--" + boundary
    last = "--" + boundary + "--"

    # XXX reading arbitrary binary data (which is possible in a file
    # upload) a line-at-a-time might be problematic.  Eg.  I have
    # observed one .GDS file in the wild where the longest "line" was
    # around 1 MB.  Most binary files that I looked at have reasonable
    # "line" lengths though -- maximum 5-10k.  However, reading in
    # fixed-size chunks would make spotting the MIME boundary tricky.
    # One more reason why HTTP upload is stupid.

    prev_delim = ""
    while 1:
        line = file.readline()

        # Hit EOF -- nothing more to read.  (This should *not* happen
        # in a well-formed MIME message, but let's assume the worst.)
        if not line:
            return 1

        # Strip (but remember) line ending.
        if line[-2:] == CRLF:
            line = line[:-2]
            delim = CRLF
        elif line[-1:] == LF:
            line = line[:-1]
            delim = LF
        else:
            delim = ""

        # If we hit the boundary line, return now.  Forget the current
        # line *and* the delimiter of the previous line -- in
        # particular, we do not want to preserve the blank line that
        # comes after an uploaded file's contents and the following
        # boundary line.
        if line == next:           # hit boundary, but more to come
            return 0
        elif line == last:         # final boundary -- no more to read
            return 1
        elif line == "Submit Query" and file.still_need(last): # workaround for flash upload
            file.finish()
            return 1

        if lines is not None:
            lines.append(line)
        if ofile is not None:
            ofile.write(prev_delim + line)
        prev_delim = delim


SAFE_CHARS = string.letters + string.digits + "-@&+=_., "
_safe_trans = None

def make_safe(s):
    global _safe_trans
    if _safe_trans is None:
        _safe_trans = ["_"] * 256
        for c in SAFE_CHARS:
            _safe_trans[ord(c)] = c
        _safe_trans = "".join(_safe_trans)

    return s.translate(_safe_trans)

# file upload counter, in case different thread in same process get same filename
counter = 0

class Upload:
    """
    Represents a single uploaded file.  Uploaded files live in the
    filesystem, *not* in memory -- this is not a file-like object!  It's
    just a place to store a couple of filenames.  Specifically, feel
    free to access the following instance attributes:

      orig_filename
        the complete filename supplied by the user-agent in the
        request that uploaded this file.  Depending on the browser,
        this might have the complete path of the original file
        on the client system, in the client system's syntax -- eg.
        "C:\foo\bar\upload_this" or "/foo/bar/upload_this" or
        "foo:bar:upload_this".
      base_filename
        the base component of orig_filename, shorn of MS-DOS,
        Mac OS, and Unix path components and with "unsafe"
        characters neutralized (see make_safe())
      tmp_filename
        where you'll actually find the file on the current system
      content_type
        the content type provided by the user-agent in the request
        that uploaded this file.
    """

    def __init__(self, orig_filename, content_type=None):
        if orig_filename:
            self.orig_filename = orig_filename
            bspos = orig_filename.rfind("\\")
            cpos = orig_filename.rfind(":")
            spos = orig_filename.rfind("/")
            if bspos != -1:                 # eg. "\foo\bar" or "D:\ding\dong"
                filename = orig_filename[bspos+1:]
            elif cpos != -1:                # eg. "C:foo" or ":ding:dong:foo"
                filename = orig_filename[cpos+1:]
            elif spos != -1:                # eg. "foo/bar/baz" or "/tmp/blah"
                filename = orig_filename[spos+1:]
            else:
                filename = orig_filename

            self.base_filename = make_safe(filename)
        else:
            self.orig_filename = None
            self.base_filename = None

        self.content_type = content_type
        self.tmp_filename = None

    def __str__(self):
        return str(self.orig_filename)

    def __repr__(self):
        return "<%s at %x: %s>" % (self.__class__.__name__, id(self), self)

    def _open(self, dir):
        """
        Generate a unique filename in 'dir'.  Open and return a
        writeable file object from it.
        """
        flags = os.O_WRONLY|os.O_CREAT|os.O_EXCL
        try:
            flags |= os.O_BINARY    # for Windows
        except AttributeError:
            pass
        tstamp = strftime("%Y%m%d.%H%M%S", localtime(time()))
        pid = os.getpid()
        global counter
        counter += 1
        while 1:
            filename = "upload.%s_%s_%s" % (pid, tstamp, counter)
            filename = os.path.join(dir, filename)
            try:
                fd = os.open(filename, flags)
            except OSError, err:
                if err.errno == errno.EEXIST:
                    # Filename collision -- try again
                    counter += 1
                else:
                    # Bomb on any other error.
                    raise
            else:
                # Opened the file just fine; it now exists so no other
                # process or thread will be able to grab that filename.
                break

        # Wrap a file object around the file descriptor.
        return (os.fdopen(fd, "wb"), filename)

    def receive(self, file, boundary, dir):
        (ofile, filename) = self._open(dir)
        done = read_mime_part(file, boundary, ofile=ofile)
        ofile.close()
        self.tmp_filename = filename
        return done

    def get_size(self):
        """get_size() : int
        Return the size of the file, measured in bytes, or None if
        the file doesn't exist.
        """
        stats = os.stat(self.tmp_filename)
        return stats.st_size


class CountingFile:
    """A file-like object that records the number of bytes read
    from the underlying file.  Ignores seek(), because it's only
    used by HTTPUploadRequest on an unseekable file (stdin).
    """

    def __init__(self, file, length):
        self.__file = file
        self.__bytesread = 0
        self.__length = int(length)

    def read(self, nbytes):
        data = self.__file.read(nbytes)
        self.__bytesread += len(data)
        return data

    def readline(self):
        line = self.__file.readline()
        self.__bytesread += len(line)
        return line

    def get_bytesread(self):
        return self.__bytesread

    def finish(self):
        self.__bytesread = self.__length

    def still_need(self, str):
        return self.__bytesread + len(str) == self.__length


class HTTPUploadRequest(HTTPRequest):
    """
    Represents a single HTTP request with Content-Type
    "multipart/form-data", which is used for HTTP uploads.  (It's
    actually possible for any HTML form to specify an encoding type of
    "multipart/form-data", even if there are no file uploads in that
    form.  In that case, you'll still get an HTTPUploadRequest object --
    but since this is a subclass of HTTPRequest, that shouldn't cause
    you any problems.)

    When processing the upload request, any uploaded files are stored
    under a temporary filename in the directory specified by the
    'upload_dir' instance attribute (which is normally set, by
    Publisher, from the UPLOAD_DIR configuration variable).
    HTTPUploadRequest then creates an Upload object which contains the
    various filenames for this upload.

    Other form variables are stored as usual in the 'form' dictionary,
    to be fetched later with get_form_var().  Uploaded files can also be
    accessed via get_form_var(), which returns the Upload object created
    at upload-time, rather than a string.

    Eg. if your upload form contains this:
      <input type="file" name="upload">

    then, when processing the form, you might do this:
      upload = request.get_form_var("upload")

    after which you could open the uploaded file immediately:
      file = open(upload.tmp_filename)

    or move it to a more permanent home before doing anything with it:
      permanent_name = os.path.join(permanent_upload_dir,
                                    upload.base_filename)
      os.rename(upload.tmp_filename, permanent_name)
    """

    def __init__(self, stdin, environ, content_type=None):
        HTTPRequest.__init__(self, stdin, environ, content_type)

        self.upload_dir = None
        self.upload_dir_mode = 0775

    def set_upload_dir(self, dir, mode=None):
        self.upload_dir = dir
        if mode is not None:
            self.upload_dir_mode = mode

    def parse_content_type(self):
        full_ctype = self.get_header('Content-Type')
        if full_ctype is None:
            raise RequestError("no Content-Type header")

        (ctype, ctype_params) = parse_header(full_ctype)
        boundary = ctype_params.get('boundary')

        if not (ctype == "multipart/form-data" and boundary):
            raise RequestError("expected Content-Type: multipart/form-data "
                               "with a 'boundary' parameter: got %r"
                               % full_ctype)

        return (ctype, boundary)

    def parse_content_disposition(self, full_cdisp):
        (cdisp, cdisp_params) = parse_header(full_cdisp)
        name = cdisp_params.get("name")

        if not (cdisp == "form-data" and name):
            raise RequestError("expected Content-Disposition: form-data "
                               "with a 'name' parameter: got %r" % full_cdisp)

        return (name, cdisp_params.get("filename"))

    def check_upload_dir(self):
        if not os.path.isdir(self.upload_dir):
            print "creating %s with mode %o" % (self.upload_dir,
                                                self.upload_dir_mode)
            os.mkdir(self.upload_dir, self.upload_dir_mode)

    def handle_upload(self, name, filename, file, boundary, content_type):
        if self.upload_dir is None:
            raise ConfigError("upload_dir not set")
        upload = Upload(filename, content_type)
        self.check_upload_dir()
        done = upload.receive(file, boundary, self.upload_dir)
        self.add_form_value(name, upload)
        return done

    def handle_regular_var(self, name, file, boundary):
        lines = []
        done = read_mime_part(file, boundary, lines=lines)
        if len(lines) == 1:
            value = lines[0]
        else:
            value = "\n".join(lines)
        self.add_form_value(name, value)
        #form_vars.append((name, value))
        return done

    def parse_body(self, file, boundary):
        total_bytes = 0                 # total bytes read from 'file'
        done = 0
        while not done:
            headers = Message(file)
            cdisp = headers.get('content-disposition')
            if not cdisp:
                raise RequestError("expected Content-Disposition header "
                                   "in body sub-part")
            (name, filename) = self.parse_content_disposition(cdisp)
            if filename:
                content_type = headers.get('content-type')
                done = self.handle_upload(name, filename, file,
                                          boundary, content_type)
            else:
                done = self.handle_regular_var(name, file, boundary)

    def check_length_read(self, file):
        # Parse Content-Length header.
        # XXX if we want to worry about disk free space, this should
        # be done *before* parsing the body!
        clen = self.get_header("Content-Length")
        if clen is not None:
            clen = int(clen)

        total_bytes = file.get_bytesread()
        if total_bytes != clen:
            raise RequestError(
                "upload request length mismatch: expected %d bytes, got %d"
                % (clen, total_bytes))

    def process_inputs(self):
        self.start_time = time()

        # Parse Content-Type header -- mainly to get the 'boundary'
        # parameter.  Barf if not there or unexpected type.
        (ctype, boundary) = self.parse_content_type()

        # The meat of the body starts after the first occurrence of
        # the boundary, so read up to that point.
        file = CountingFile(self.stdin, self.get_header("Content-Length"))
        read_mime_part(file, boundary)

        # Parse the parts of the message, ie. the form variables.  Some of
        # these will presumably be "file upload" variables, so need to be
        # treated specially.
        self.parse_body(file, boundary)

        # Ensure that we read exactly as many bytes as were promised
        # by the Content-Length header.
        self.check_length_read(file)
