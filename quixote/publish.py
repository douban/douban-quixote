"""quixote.publish
$HeadURL: svn+ssh://svn/repos/trunk/quixote/publish.py $
$Id$

Logic for publishing modules and objects on the Web.
"""

__revision__ = "$Id$"

import sys, os, traceback, cStringIO
import time, types, socket, re, warnings
import struct
try:
    import zlib # for COMPRESS_PAGES option
    import binascii
except ImportError:
    pass
import threading

from quixote import errors
from quixote.html import htmltext
from quixote.http_request import HTTPRequest, HTTPJSONRequest, get_content_type
from quixote.http_response import HTTPResponse, Stream
from quixote.upload import HTTPUploadRequest, Upload
from quixote.sendmail import sendmail

try:
    import cgitb                        # Only available in Python 2.2
except ImportError:
    cgitb = None

def _get_module(name):
    """Get a module object by name."""
    __import__(name)
    module = sys.modules[name]
    return module

# Error message to dispay when DISPLAY_EXCEPTIONS in config file is not
# true.  Note that SERVER_ADMIN must be fetched from the environment and
# plugged in here -- we can't do it now because the environment isn't
# really setup for us yet if running as a FastCGI script.
INTERNAL_ERROR_MESSAGE = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN"
        "http://www.w3.org/TR/REC-html40/strict.dtd">
<html>
<head><title>Internal Server Error</title></head>
<body>
<h1>Internal Server Error</h1>
<p>An internal error occurred while handling your request.</p>

<p>The server administrator should have been notified of the problem.
You may wish to contact the server administrator (%s) and inform them of
the time the error occurred, and anything you might have done to trigger
the error.</p>

<p>If you are the server administrator, more information may be
available in either the server's error log or Quixote's error log.</p>
</body>
</html>
"""

class Publisher:
    """
    The core of Quixote and of any Quixote application.  This class is
    responsible for converting each HTTP request into a search of
    Python's package namespace and, ultimately, a call of a Python
    function/method/callable object.

    Each invocation of a driver script should have one Publisher
    instance that lives for as long as the driver script itself.  Eg. if
    your driver script is plain CGI, each Publisher instance will handle
    exactly one HTTP request; if you have a FastCGI driver, then each
    Publisher will handle every HTTP request handed to that driver
    script process.

    Instance attributes:
      root_namespace : module | instance | class
        the Python namespace that will be searched for objects to
        fulfill each HTTP request
      exit_now : boolean
        used for internal state management.  If true, the loop in
        publish_cgi() will terminate at the end of the current request.
      access_log : file
        file to which every access will be logged; set by
        setup_logs() (None if no access log)
      error_log : file
        file to which application errors (exceptions caught by Quixote,
        as well as anything printed to stderr by application code) will
        be logged; set by setup_logs().  Set to sys.stderr if no
        ERROR_LOG setting in the application config file.
      config : Config
        holds all configuration info for this application.  If the
        application doesn't have a config file, uses the default values
        from the quixote.config module.
      _request : HTTPRequest
        the HTTP request currently being processed.
      namespace_stack : [ module | instance | class ]
    """

    def __init__(self, root_namespace, config=None):
        from quixote.config import Config

        # if more than one publisher in app, need to set_publisher per request
        set_publisher(self)

        if type(root_namespace) is types.StringType:
            self.root_namespace = _get_module(root_namespace)
        else:
            # Should probably check that root_namespace is really a
            # namespace, ie. a module, class, or instance -- but it's
            # tricky to know if something is really a class or instance
            # (because of ExtensionClass), and who knows what other
            # namespaces are lurking out there in the world?
            self.root_namespace = root_namespace

        # for PublishError exception handling
        self.namespace_stack = [self.root_namespace]

        self.exit_now = 0
        self.access_log = None
        self.error_log = sys.stderr     # possibly overridden in setup_logs()
        sys.stdout = self.error_log     # print is handy for debugging

        # Initialize default config object with all the default values from
        # the config variables at the top of the config module, ie. if
        # ERROR_LOG is set to "/var/log/quxiote-error.log", then
        # config.ERROR_LOG will also be "/var/log/quixote-error.log".  If
        # application FCGI/CGI scripts need to override any of these
        # defaults, they can do so by direct manipulation of the config
        # object, or by reading a config file:
        #   app.read_config("myapp.conf")
        if config is None:
            self.config = Config()
        else:
            self.set_config(config)

        self._local = threading.local()

    @property
    def _request(self):
        warnings.warn("use get_request instead of _request")
        return self.get_request()

    def configure(self, **kwargs):
        self.config.set_from_dict(kwargs)

    def read_config(self, filename):
        self.config.read_file(filename)

    def set_config(self, config):
        from quixote.config import Config
        if not isinstance(config, Config):
            raise TypeError, "'config' must be a Config instance"
        self.config = config

    def setup_logs(self):
        """
         Open all log files specified in the config file. Reassign
        sys.stderr to go to the error log, and sys.stdout to go to
        the debug log.
        """

        if self.config.access_log is not None:
            try:
                self.access_log = open(self.config.access_log, 'a', 1)
            except IOError, exc:
                sys.stderr.write("error opening access log %s: %s\n"
                                 % (`self.config.access_log`, exc.strerror))

        if self.config.error_log is not None:
            try:
                self.error_log = open(self.config.error_log, 'a', 1)
                sys.stderr = self.error_log
            except IOError, exc:
                # leave self.error_log as it was, most likely sys.stderr
                sys.stderr.write("error opening error log %s: %s\n"
                                 % (`self.config.error_log`, exc.strerror))

        if self.config.debug_log is not None:
            try:
                debug_log = open(self.config.debug_log, 'a', 1)
                sys.stdout = debug_log
            except IOError, exc:
                sys.stderr.write("error opening debug log %s: %s\n"
                                 % (`self.config.debug_log`, exc.strerror))


    def shutdown_logs(self):
        """
        Close log files and restore sys.stdout and sys.stderr to their
        original values.
        """
        if sys.stdout is sys.__stdout__:
            raise RuntimeError, "'setup_logs()' never called"
        if sys.stdout is not sys.stderr:
            sys.stdout.close()
        sys.stdout = sys.__stdout__
        self.access_log.close()
        if self.error_log is not sys.__stderr__:
            self.error_log.close()
            sys.stderr = sys.__stderr__

    def log(self, msg):
        """
        Write an message to the error log with a time stamp.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(time.time()))
        self.error_log.write("[%s] %s\n" % (timestamp, msg))

    debug = log # backwards compatibility

    def create_request(self, stdin, env):
        ctype = get_content_type(env)
        if ctype == "multipart/form-data" and (
                    # workaround for safari bug, see ticket #1556
                    env.get('REQUEST_METHOD') != 'GET'
                    or env.get('CONTENT_LENGTH', '0') != '0'
                ):
            req = HTTPUploadRequest(stdin, env, content_type=ctype)
            req.set_upload_dir(self.config.upload_dir,
                               self.config.upload_dir_mode)
            return req
        elif self.config.support_application_json and ctype == "application/json":
            return HTTPJSONRequest(stdin, env, content_type=ctype)
        else:
            return HTTPRequest(stdin, env, content_type=ctype)

    def parse_request(self, request):
        """Parse the request information waiting in 'request'.
        """
        request.process_inputs()

    def start_request(self, request):
        """Called at the start of each request.  Overridden by
        SessionPublisher to handle session details.
        """
        pass

    def _set_request(self, request):
        """Set the current request object.
        """
        self._local.request = request

    def _clear_request(self):
        """Unset the current request object.
        """
        request = self._local.request
        if request:
        # clear upload file
            for k, v in request.form.items():
                if isinstance(v, Upload):
                    try:
                        os.remove(v.tmp_filename)
                    except OSError:
                        pass
        self._local.request = None

    def get_request(self):
        """Return the current request object.
        """
        return self._local.request

    def log_request(self, request):
        """Log a request in the access_log file.
        """
        if self.access_log is not None:
            if request.session:
                user = request.session.user or "-"
            else:
                user = "-"
            now = time.time()
            seconds = now - request.start_time
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))

            env = request.environ

            # Under Apache, REQUEST_URI == SCRIPT_NAME + PATH_INFO.
            # Not everyone uses Apache, so we have to stick to
            # environment variables in the CGI spec.  Note that this
            # relies on PATH_INFO under IIS being fixed by HTTPRequest,
            # because IIS gets it wrong.
            request_uri = env.get('SCRIPT_NAME') + env.get('PATH_INFO', '')
            query = env.get('QUERY_STRING', '')
            if query:
                query = "?" + query
            proto = env.get('SERVER_PROTOCOL')

            self.access_log.write('%s %s %s %d "%s %s %s" %s %r %0.2fsec\n' %
                                   (request.environ.get('REMOTE_ADDR'),
                                    str(user),
                                    timestamp,
                                    os.getpid(),
                                    request.get_method(),
                                    request_uri + query,
                                    proto,
                                    request.response.status_code,
                                    request.environ.get('HTTP_USER_AGENT', ''),
                                    seconds
                                   ))


    def finish_successful_request(self, request):
        """Called at the end of a successful request.  Overridden by
        SessionPublisher to handle session details."""
        pass

    def finish_interrupted_request(self, request, exc):
        """
        Called at the end of an interrupted request.  Requests are
        interrupted by raising a PublishError exception.  This method
        should return a string object which will be used as the result of
        the request.

        This method searches for the nearest namespace with a
        _q_exception_handler attribute.  That attribute is expected to be
        a function and is called with the request and exception instance
        as arguments and should return the error page (e.g. a string).  If
        the handler doesn't want to handle a particular error it can
        re-raise it and the next nearest handler will be found.  If no
        _q_exception_handler is found, the default Quixote handler is
        used.
        """

        # Throw away the existing response object and start a new one
        # for the error document we're going to create here.
        request.response = HTTPResponse()

        # set response status code so every custom doesn't have to do it
        request.response.set_status(exc.status_code)

        if self.config.secure_errors and exc.private_msg:
            exc.private_msg = None # hide it

        # walk up stack and find handler for the exception
        stack = self.namespace_stack[:]
        while 1:
            handler = None
            while stack:
                object = stack.pop()
                if hasattr(object, "_q_exception_handler"):
                    handler = object._q_exception_handler
                    break
            if handler is None:
                handler = errors.default_exception_handler

            try:
                return handler(request, exc)
            except errors.PublishError:
                assert handler is not errors.default_exception_handler
                continue # exception was re-raised or another exception occured


    def finish_failed_request(self, request):
        """
        Called at the end of an failed request.  Any exception (other
        than PublishError) causes a request to fail.  This method should
        return a string object which will be used as the result of the
        request.
        """
        # build new response to be safe
        original_response = request.response
        request.response = HTTPResponse()
        #self.log("caught an error (%s), reporting it." %
        #         sys.exc_info()[1])

        (exc_type, exc_value, tb) = sys.exc_info()
        error_summary = traceback.format_exception_only(exc_type, exc_value)
        error_summary = error_summary[0][0:-1] # de-listify and strip newline

        plain_error_msg = self._generate_plaintext_error(request,
                                                         original_response,
                                                         exc_type, exc_value,
                                                         tb)

        if not self.config.display_exceptions:
            # DISPLAY_EXCEPTIONS is false, so return the most
            # secure (and cryptic) page.
            request.response.set_header("Content-Type", "text/html")
            user_error_msg = self._generate_internal_error(request)
        elif self.config.display_exceptions == 'html' and cgitb is not None:
            # Generate a spiffy HTML display using cgitb
            request.response.set_header("Content-Type", "text/html")
            user_error_msg = self._generate_cgitb_error(request,
                                                        original_response,
                                                        exc_type, exc_value,
                                                        tb)
        else:
            # Generate a plaintext page containing the traceback
            request.response.set_header("Content-Type", "text/plain")
            user_error_msg = plain_error_msg

        self.log("exception caught")
        self.error_log.write(plain_error_msg)

        if self.config.error_email:
            self.mail_error(plain_error_msg, error_summary)

        request.response.set_status(500)
        return user_error_msg


    def _generate_internal_error(self, request):
        admin = request.environ.get('SERVER_ADMIN',
                                    "<i>email address unknown</i>")
        return INTERNAL_ERROR_MESSAGE % admin


    def _generate_plaintext_error(self, request, original_response,
                                  exc_type, exc_value, tb):
        error_file = cStringIO.StringIO()

        # format the traceback
        traceback.print_exception(exc_type, exc_value, tb, file=error_file)

        # include request and response dumps
        error_file.write('\n')
        error_file.write(request.dump())
        error_file.write('\n')

        return error_file.getvalue()


    def _generate_cgitb_error(self, request, original_response,
                              exc_type, exc_value, tb):
        error_file = cStringIO.StringIO()
        hook = cgitb.Hook(file=error_file)
        hook(exc_type, exc_value, tb)
        error_file.write('<h2>Original Request</h2>')
        error_file.write(request.dump_html())
        error_file.write('<h2>Original Response</h2><pre>')
        original_response.write(error_file)
        error_file.write('</pre>')
        return error_file.getvalue()


    def mail_error(self, msg, error_summary):
        """Send an email notifying someone of a traceback."""
        sendmail('Quixote Traceback (%s)' % error_summary,
                 msg, [self.config.error_email],
                 from_addr=(self.config.error_email, socket.gethostname()))

    def get_namespace_stack(self):
        """get_namespace_stack() ->  [ module | instance | class ]
        """
        return self.namespace_stack

    def try_publish(self, request, path):
        """try_publish(request : HTTPRequest, path : string) -> string

        The master method that does all the work for a single request.  Uses
        traverse_url() to get a callable object.  The object is called and
        the output is returned.  Exceptions are handled by the caller.
        """

        self.start_request(request)

        # Initialize the publisher's namespace_stack
        self.namespace_stack = []

        # Traverse package to a (hopefully-) callable object
        object = _traverse_url(self.root_namespace, path, request,
                               self.config.fix_trailing_slash,
                               self.namespace_stack)

        # None means no output -- traverse_url() just issued a redirect.
        if object is None:
            return None

        # Anything else must be either a string...
        if isstring(object):
            output = object

        # ...or a callable.
        elif callable(object) or hasattr(object, "__call__"):
            try:
                if callable(object):
                    output = object(request)
                else:
                    output = object.__call__(request)
            except SystemExit:
                output = "SystemExit exception caught, shutting down"
                self.log(output)
                self.exit_now = 1

            if output is None:
                raise RuntimeError, 'callable %s returned None' % repr(object)

        # Uh-oh: 'object' is neither a string nor a callable.
        else:
            raise RuntimeError(
                "object is neither callable nor a string: %s" % repr(object))


        # The callable ran OK, commit any changes to the session
        self.finish_successful_request(request)

        return output

    _GZIP_HEADER = ("\037\213" # magic
                    "\010" # compression method
                    "\000" # flags
                    "\000\000\000\000" # time, who cares?
                    "\002"
                    "\377")

    _GZIP_THRESHOLD = 200 # responses smaller than this are not compressed

    def compress_output(self, request, output):
        encoding = request.get_encoding(["gzip", "x-gzip"])
        n = len(output)
        if n > self._GZIP_THRESHOLD and encoding:
            co = zlib.compressobj(6, zlib.DEFLATED, -zlib.MAX_WBITS,
                                  zlib.DEF_MEM_LEVEL, 0)
            chunks = [self._GZIP_HEADER,
                      co.compress(output),
                      co.flush(),
                      struct.pack("<ll", binascii.crc32(output), len(output))]
            output = "".join(chunks)
            #self.log("gzip (original size %d, ratio %.1f)" %
            #           (n, float(n)/len(output)))
            request.response.set_header("Content-Encoding", encoding)
        return output

    def filter_output(self, request, output):
        """Hook for post processing the output.  Subclasses may wish to
        override (e.g. check HTML syntax).
        """
        if (output and
                self.config.compress_pages and
                not isinstance(output, Stream)):
            output = self.compress_output(request, str(output))
        return output

    def process_request(self, request, env):
        """process_request(request : HTTPRequest, env : dict) : string

        Process a single request, given an HTTPRequest object.  The
        try_publish() method will be called to do the work and
        exceptions will be handled here.
        """
        self._set_request(request)
        try:
            self.parse_request(request)
            output = self.try_publish(request, env.get('PATH_INFO', ''))
        except errors.PublishError, exc:
            # Exit the publishing loop and return a result right away.
            output = self.finish_interrupted_request(request, exc)
        except:
            # Some other exception, generate error messages to the logs, etc.
            output = self.finish_failed_request(request)
        output = self.filter_output(request, output)
        self.log_request(request)
        return output

    def publish(self, stdin, stdout, stderr, env):
        """publish(stdin : file, stdout : file, stderr : file, env : dict)

        Create an HTTPRequest object from the environment and from
        standard input, process it, and write the response to standard
        output.
        """
        request = self.create_request(stdin, env)
        output = self.process_request(request, env)

        # Output results from Response object
        if output:
            request.response.set_body(output)
        try:
            request.response.write(stdout)
        except IOError, exc:
            self.log('IOError caught while writing request (%s)' % exc)
        self._clear_request()


    def publish_cgi(self):
        """publish_cgi()

        Entry point from CGI scripts; it will execute the publish function
        once and return.
        """
        if sys.platform == "win32":
            # on Windows, stdin and stdout are in text mode by default
            import msvcrt
            msvcrt.setmode(sys.__stdin__.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.__stdout__.fileno(), os.O_BINARY)
        self.publish(sys.__stdin__, sys.__stdout__, sys.__stderr__, os.environ)

    def publish_fcgi(self):
        """publish_fcgi()

        Entry point from FCGI scripts; it will repeatedly do the publish()
        function until there are no more requests.  This should also work
        for CGI scripts but it is not as portable as publish_cgi().
        """
        from quixote import fcgi
        while fcgi.isFCGI() and not self.exit_now:
            f = fcgi.FCGI()
            self.publish(f.inp, f.out, f.err, f.env)
            f.Finish()
            if self.config.run_once:
                break


# class Publisher


class SessionPublisher(Publisher):

    def __init__(self, root_namespace, config=None, session_mgr=None):
        from quixote.session import SessionManager
        Publisher.__init__(self, root_namespace, config)
        if session_mgr is None:
            self.session_mgr = SessionManager()
        else:
            self.session_mgr = session_mgr

    def set_session_manager(self, session_mgr):
        self.session_mgr = session_mgr

    def start_request(self, request):
        # Get the session object and stick it onto the request
        request.session = self.session_mgr.get_session(request)
        request.session.start_request(request)

    def finish_successful_request(self, request):
        if request.session is not None:
            request.session.finish_request(request)
            self.session_mgr.maintain_session(request, request.session)
        self.session_mgr.commit_changes(request.session)

    def finish_interrupted_request(self, request, exc):
        output = Publisher.finish_interrupted_request(self, request, exc)

        # commit the current transaction so that any changes to the
        # session objects are saved and are visible on the next HTTP
        # hit.  Remember, AccessError is a subclass of PublishError,
        # so this code will be run for both typos in the URL and for
        # the user not being logged in.
        #
        # The assumption here is that the UI code won't make changes
        # to the core database before checking permissions and raising
        # a PublishError; if you must do this (though it's hard to see
        # why this would be necessary), you'll have to abort the
        # current transaction, make your session changes, and then
        # raise the PublishError.
        #
        # XXX We should really be able to commit session changes and
        # database changes separately, but that requires ZODB
        # incantations that we currently don't know.
        self.session_mgr.commit_changes(request.session)

        return output

    def finish_failed_request(self, request):
        if self.session_mgr:
            self.session_mgr.abort_changes(request.session)
        return Publisher.finish_failed_request(self, request)

# class SessionPublisher

_slash_pat = re.compile("//*")

def _traverse_url(root_namespace, path, request, fix_trailing_slash,
                  namespace_stack):
    """traverse_url(root_namespace : any, path : string,
                    request : HTTPRequest, fix_trailing_slash : bool,
                    namespace_stack : list) -> (object : any)

    Perform traversal based on the provided path, starting at the root
    object.  It returns the script name and path info values for
    the arrived-at object, along with the object itself and
    a list of the namespaces traversed to get there.

    It's expected that the final object is something callable like a
    function or a method; intermediate objects along the way will
    usually be packages or modules.

    To prevent crackers from writing URLs that traverse private
    objects, every package, module, or object along the way must have
    a _q_exports attribute containing a list of publicly visible
    names.  Not having a _q_exports attribute is an error, though
    having _q_exports be an empty list is OK.  If a component of the path
    isn't in _q_exports, that also produces an error.

    Modifies the namespace_stack as it traverses the url, so that
    any exceptions encountered along the way can be handled by the
    nearest handler.
    """

    # If someone accesses a Quixote driver script without a trailing
    # slash, we'll wind up here with an empty path.  This won't
    # work; relative references in the page generated by the root
    # namespace's _q_index() will be off.  Fix it by redirecting the
    # user to the right URL; when the client follows the redirect,
    # we'll wind up here again with path == '/'.
    if (not path and fix_trailing_slash):
        request.redirect(request.environ['SCRIPT_NAME'] + '/' ,
                         permanent=1)
        return None

    # replace repeated slashes with a single slash
    if path.find("//") != -1:
        path = _slash_pat.sub("/", path)

    # split path apart; /foo/bar/baz  -> ['foo', 'bar', 'baz']
    #                   /foo/bar/     -> ['foo', 'bar', '']
    path_components = path[1:].split('/')

    # Traverse starting at the root
    object = root_namespace
    namespace_stack.append(object)

    # Loop over the components of the path
    for component in path_components:
        if component == "":
            # "/q/foo/" == "/q/foo/_q_index"
            if (callable(object) or isstring(object)) and \
                        request.get_method() == "GET" and fix_trailing_slash:
                # drop last "/", then redirect
                if 'REQUEST_URI' in request.environ:
                    uri = request.environ['REQUEST_URI']
                    idx = uri.find('?')
                    new_uri = uri[:idx-1] + uri[idx:] if idx > 0 else uri[:-1]
                else:
                    query = request.environ.get('QUERY_STRING', '')
                    new_uri = request.get_path()[:-1] + (query and "?" + query)
                return request.redirect(new_uri, permanent=1)
            component = "_q_index"
        object = _get_component(object, component, path, request,
                               namespace_stack)

    if not (isstring(object) or callable(object) or hasattr(object, '__call__')):
        # We went through all the components of the path and ended up at
        # something which isn't callable, like a module or an instance
        # without a __call__ method.
        if path[-1] != '/' :
            _obj = _get_component(object, "_q_index", path, request,
                               namespace_stack)
            if (callable(_obj) or isstring(_obj)) and \
                    request.get_method() == "GET" and fix_trailing_slash:
                # This is for the convenience of users who type in paths.
                # Repair the path and redirect.  This should not happen for
                # URLs within the site.
                if 'REQUEST_URI' in request.environ:
                    uri = request.environ['REQUEST_URI']
                    idx = uri.find('?')
                    new_uri = uri[:idx] + '/' + uri[idx:] if idx > 0 else uri + '/'
                else:
                    query = request.environ.get('QUERY_STRING', '')
                    new_uri = request.get_path() + '/' + (query and "?" + query)
                return request.redirect(new_uri, permanent=1)

        raise errors.TraversalError(
                "object is neither callable nor string",
                private_msg=repr(object),
                path=path)

    return object


def _lookup_export(name, exports):
    """Search an exports list for a name.  Returns the internal name for
    'name' or return None if 'name' is not in 'exports'.

    Each element of the export list can be either a string or a 2-tuple
    of strings that maps an external name into internal name.  The
    mapping is useful when the desired external name is not a valid
    Python identifier.
    """
    for value in exports:
        if value == name:
            internal_name = name
            break
        elif type(value) is types.TupleType:
            if value[0] == name:
                internal_name = value[1] # internal name is different
                break
    else:
        if name == '_q_index':
            internal_name = name # _q_index does not need to be in exports list
        else:
            internal_name = None # not found in exports
    return internal_name


def _get_component(container, component, path, request, namespace_stack):
    """Get one component of a path from a namespace.
    """
    # First security check: if the container doesn't even have an
    # _q_exports list, fail now: all Quixote-traversable namespaces
    # (modules, packages, instances) must have an export list!
    if not hasattr(container, '_q_exports'):
        raise errors.TraversalError(
                    private_msg="%r has no _q_exports list" % container)

    # Second security check: call _q_access function if it's present.
    if hasattr(container, '_q_access'):
        # will raise AccessError if access failed
        container._q_access(request)

    # Third security check: make sure the current name component
    # is in the export list or is '_q_index'.  If neither
    # condition is true, check for a _q_lookup() and call it.
    # '_q_lookup()' translates an arbitrary string into an object
    # that we continue traversing.  (This is very handy; it lets
    # you put user-space objects into your URL-space, eliminating
    # the need for digging ID strings out of a query, or checking
    # PATHINFO after Quixote's done with it.  But it is a
    # compromise to security: it opens up the traversal algorithm
    # to arbitrary names not listed in _q_exports!)  If
    # _q_lookup() doesn't exist or is None, a TraversalError is
    # raised.

    # Check if component is in _q_exports.  The elements in
    # _q_exports can be strings or 2-tuples mapping external names
    # to internal names.
    if component in container._q_exports or component == '_q_index':
        internal_name = component
    else:
        # check for an explicit external to internal mapping
        for value in container._q_exports:
            if type(value) is types.TupleType:
                if value[0] == component:
                    internal_name = value[1]
                    break
        else:
            internal_name = None

    if internal_name is None:
        # Component is not in exports list.
        object = None
        if hasattr(container, "_q_lookup"):
            object = container._q_lookup(request, component)
        elif hasattr(container, "_q_getname"):
            warnings.warn("_q_getname() on %s used; should "
                          "be replaced by _q_lookup()" % type(container))
            object = container._q_getname(request, component)
        if object is None:
            raise errors.TraversalError(
                private_msg="object %r has no attribute %r" % (
                                                    container,
                                                    component))

    # From here on, you can assume that the internal_name is not None
    elif hasattr(container, internal_name):
        # attribute is in _q_exports and exists
        object = getattr(container, internal_name)

    elif internal_name == '_q_index':
        if hasattr(container, "_q_lookup"):
            object = container._q_lookup(request, "")
        else:
            raise errors.AccessError(
                private_msg=("_q_index not found in %r" % container))

    elif hasattr(container, "_q_resolve"):
        object = container._q_resolve(internal_name)
        if object is None:
            raise RuntimeError, ("component listed in _q_exports, "
                                 "but not returned by _q_resolve(%r)"
                                 % internal_name)
        else:
            # Set the object, so _q_resolve won't need to be called again.
            setattr(container, internal_name, object)

    elif type(container) is types.ModuleType:
        # try importing it as a sub-module.  If we get an ImportError
        # here we don't catch it.  It means that something that
        # doesn't exist was exported or an exception was raised from
        # deeper in the code.
        mod_name = container.__name__ + '.' + internal_name
        object = _get_module(mod_name)

    else:
        # a non-existent attribute is in _q_exports,
        # and the container is not a module.  Give up.
        raise errors.TraversalError(
                private_msg=("%r in _q_exports list, "
                             "but not found in %r" % (component,
                                                      container)))

    namespace_stack.append(object)
    return object



class PublisherProxy(object):
    def __init__(self):
        self.local = threading.local()

    def set_publisher(self, publisher):
        self.local.publisher = publisher

    def __getattr__(self, name):
        return getattr(self.local.publisher, name)

_publisher = PublisherProxy()

def get_publisher():
    global _publisher
    return _publisher

def set_publisher(publisher):
    global _publisher
    _publisher.set_publisher(publisher)

def get_request():
    global _publisher
    return _publisher.get_request()

def get_path(n=0):
    global _publisher
    return _publisher.get_request().get_path(n)

def redirect(location, permanent=0):
    global _publisher
    return _publisher.get_request().redirect(location, permanent)

def get_session():
    global _publisher
    return _publisher.get_request().session

def get_session_manager():
    global _publisher
    return _publisher.session_mgr

def get_user():
    global _publisher
    session = _publisher.get_request().session
    if session is None:
        return None
    else:
        return session.user


if sys.hexversion >= 0x02020000:    # Python 2.2 or greater
    def isstring(x):
        return isinstance(x, (str, unicode, htmltext))
else:
    if hasattr(types, 'UnicodeType'):
        _string_types = (types.StringType, types.UnicodeType)
    else:
        _string_types = (types.StringType,)

    def isstring(x):
        return type(x) in _string_types
