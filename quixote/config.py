"""quixote.config
$HeadURL: svn+ssh://svn/repos/trunk/quixote/config.py $
$Id$

Quixote configuration information.  This module provides both the
default configuration values, and some code that Quixote uses for
dealing with configuration info.  You should not edit the configuration
values in this file, since your edits will be lost if you upgrade to a
newer Quixote version in the future.  However, this is the canonical
source of information about Quixote configuration variables, and editing
the defaults here is harmless if you're just playing around and don't
care what happens in the future.
"""

__revision__ = "$Id$"


# Note that the default values here are geared towards a production
# environment, preferring security and performance over verbosity and
# debug-ability.  If you just want to get a Quixote application
# up-and-running in a production environment, these settings are mostly
# right; all you really need to customize are ERROR_EMAIL, and ERROR_LOG.
# If you need to test/debug/develop a Quixote application, though, you'll
# probably want to also change DISPLAY_EXCEPTIONS, SECURE_ERRORS, and
# maybe RUN_ONCE.  Again, you shouldn't edit this file unless you don't
# care what happens in the future (in particular, an upgrade to Quixote
# would clobber your edits).


# E-mail address to send application errors to; None to send no mail at
# all.  This should probably be the email address of your web
# administrator.
ERROR_EMAIL = None
#ERROR_EMAIL = 'webmaster@example.com'

# Filename for writing the Quixote access log; None for no access log.
ACCESS_LOG = None
#ACCESS_LOG = "/www/log/quixote-access.log"

# Filename for logging error messages; if None, everything will be sent
# to standard error, so it should wind up in the Web server's error log
# file.
ERROR_LOG = None

# Filename for logging debugging output; if None then debugging output
# goes to the error log. (Anything that application code prints to
# stdout is debug output.)
DEBUG_LOG = None

# Controls what's done when uncaught exceptions occur.  If set to
# 'plain', the traceback will be returned to the browser in addition
# to being logged, If set to 'html' and the cgitb module is installed,
# a more elaborate display will be returned to the browser, showing
# the local variables and a few lines of context for each level of the
# traceback.  If set to None, a generic error display, containing no
# information about the traceback, will be used.
#
# It is convenient to enable this on development servers.  On publicly
# accessible servers it should be disabled for security reasons.
#
# (For backward compatibility reasons, 0 and 1 are also legal values
# for this setting.)
DISPLAY_EXCEPTIONS = None

# If set to True, Quixote will not catch exceptions, and
# exceptions will propagate upwards.
DEBUG_PROPAGATE_EXCEPTIONS = False

# If true, then any "resource not found" errors will result in a
# consistent, terse, mostly-useless message.  If false, then the
# exact cause of failure will be returned.
SECURE_ERRORS = 1

# If true, Quixote will service exactly one request at a time, and
# then exit.  This makes no difference when you're running as a
# straight CGI script, but it makes it easier to debug while running
# as a FastCGI script.
RUN_ONCE = 0

# Automatically redirect paths referencing non-callable objects to a path
# with a trailing slash.  This is convienent for external users of the
# site but should be disabled for development.  Internal links on the
# site should not require redirects.  They are costly, especially on high
# latency links like dialup lines.
FIX_TRAILING_SLASH = 1

# Compress large pages using gzip if the client accepts that encoding.
COMPRESS_PAGES = 0

# If true, then a cryptographically secure token will be inserted into forms
# as a hidden field.  The token will be checked when the form is submitted.
# This prevents cross-site request forgeries (CSRF).  It is off by default
# since it doesn't work if sessions are not persistent across requests.
FORM_TOKENS = 0

# If true, the remote IP address of requests will be checked against the
# IP address that created the session; this is a defense against playback
# attacks.  It will frustrate mobile laptop users, though.
CHECK_SESSION_ADDR = 0

# If true, the content of request of which content-type is application/json will be directly unseriliazed into request.json.
# It can also be accessed through request.form and form-releated interface(such as get_form_var) when its type is JSON object
SUPPORT_APPLICATION_JSON = 0

# Session-related variables
# =========================

# Name of the cookie that will hold the session ID string.
SESSION_COOKIE_NAME = "QX_session"

# Domain and path to which the session cookie is restricted.  Leaving
# these undefined is fine.  Quixote does not have a default "domain"
# option, meaning the session cookie will only be sent to the
# originating server.  If you don't set the cookie path, Quixote will
# use your application's root URL (ie. SCRIPT_NAME in a CGI-like
# environment), meaning the session cookie will be sent to all URLs
# controlled by your application, but no other.
SESSION_COOKIE_DOMAIN = None    # eg. ".example.com"
SESSION_COOKIE_PATH = None      # eg. "/"


# Mail-related variables
# ======================
# These are only used by the quixote.sendmail module, which is
# provided for use by Quixote applications that need to send
# e-mail.  This is a common task for web apps, but by no means
# universal.
#
# E-mail addresses can be specified either as a lone string
# containing a bare e-mail address ("addr-spec" in the RFC 822
# grammar), or as an (address, real_name) tuple.

# MAIL_FROM is used as the default for the "From" header and the SMTP
# sender for all outgoing e-mail.  If you don't set it, your application
# will crash the first time it tries to send e-mail without an explicit
# "From" address.
MAIL_FROM = None     # eg. "webmaster@example.com"
                     # or  ("webmaster@example.com", "Example Webmaster")

# E-mail is sent by connecting to an SMTP server on MAIL_SERVER.  This
# server must be configured to relay outgoing e-mail from the current
# host (ie., the host where your Quixote application runs, most likely
# your web server) to anywhere on the Internet.  If you don't know what
# this means, talk to your system administrator.
MAIL_SERVER = "localhost"

# If MAIL_DEBUG_ADDR is set, then all e-mail will actually be sent to
# this address rather than the intended recipients.  This should be a
# single, bare e-mail address.
MAIL_DEBUG_ADDR = None   # eg. "developers@example.com"


# HTTP file upload variables
# ==========================

# Any files upload via HTTP will be written to temporary files
# in UPLOAD_DIR.  If UPLOAD_DIR is not defined, any attempts to
# upload via HTTP will crash (ie. uncaught exception).
UPLOAD_DIR = None

# If UPLOAD_DIR does not exist, Quixote will create it with
# mode UPLOAD_DIR_MODE.  No idea what this should be on Windows.
UPLOAD_DIR_MODE = 0755


# -- End config variables ----------------------------------------------
# (no user serviceable parts after this point)

# Note that this module is designed to not export any names apart from
# the above config variables and the following Config class -- hence,
# all imports are done in local scopes.  This allows application config
# modules to safely say "from quixote.config import *".

class ConfigError(Exception):

    def __init__(self, msg, source=None, var=None):
        self.msg = msg
        self.source = source
        self.var = var

    def __str__(self):
        chunks = []
        if self.source:
            chunks.append(self.source)
        if self.var:
            chunks.append(self.var)
        chunks.append(self.msg)
        return ": ".join(chunks)


class Config:
    """Holds all Quixote configuration variables -- see above for
    documentation of them.  The naming convention is simple:
    downcase the above variables to get the names of instance
    attributes of this class.
    """

    config_vars = [
        'error_email',
        'access_log',
        'debug_log',
        'display_exceptions',
        'debug_propagate_exceptions',
        'secure_errors',
        'error_log',
        'run_once',
        'fix_trailing_slash',
        'compress_pages',
        'form_tokens',
        'session_cookie_domain',
        'session_cookie_name',
        'session_cookie_path',
        'check_session_addr',
        'mail_from',
        'mail_server',
        'mail_debug_addr',
        'upload_dir',
        'upload_dir_mode',
        'support_application_json',
        ]


    def __init__(self, read_defaults=1):
        for var in self.config_vars:
            setattr(self, var, None)
        if read_defaults:
            self.read_defaults()

    def __setattr__(self, attr, val):
        if not attr in self.config_vars:
            raise AttributeError, "no such configuration variable: %s" % `attr`
        self.__dict__[attr] = val


    def dump(self, file=None):
        import sys
        if file is None:
            file = sys.stdout
        file.write("<%s.%s instance at %x>:\n" %
                   (self.__class__.__module__,
                    self.__class__.__name__,
                    id(self)))
        for var in self.config_vars:
            file.write("  %s = %s\n" % (var, `getattr(self, var)`))


    def set_from_dict(self, dict, source=None):
        import string, re
        ucstring_re = re.compile(r'^[A-Z_]+$')

        for (var, val) in dict.items():
            if ucstring_re.match(var):
                setattr(self, string.lower(var), val)

        self.check_values(source)

    def check_values(self, source):
        """
        check_values(source : string)

        Check the configuration variables to ensure that they
        are all valid.  Raise ConfigError with 'source' as the
        second argument if any problems are found.
        """
        # Check value of DISPLAY_EXCEPTIONS.  Values that are
        # equivalent to 'false' are set to None; a value of 1
        # is changed to 'plain'.
        if not self.display_exceptions:
            self.display_exceptions = None
        elif self.display_exceptions == 1:
            self.display_exceptions = 'plain'
        if self.display_exceptions not in (None, 'plain', 'html'):
            raise ConfigError("Must be None,"
                              " 'plain', or 'html'",
                              source,
                              "DISPLAY_EXCEPTIONS")


    def read_file(self, filename):
        """Read configuration from a file.  Any variables already
        defined in this Config instance, but not in the file, are
        unchanged, so you can use this to build up a configuration
        by accumulating data from several config files.
        """
        # The config file is Python code -- makes life easy.
        config_vars = {}
        try:
            execfile(filename, config_vars)
        except IOError, exc:
            if exc.filename is None:    # arg! execfile() loses filename
                exc.filename = filename
            raise exc

        self.set_from_dict(config_vars, source=filename)

    def read_from_module(self, modname):
        """Read configuration info from a Python module (default
        is the module where the Config class is defined, ie.
        quixote.config).  Also accumulates config data, just like
        'read_file()'.
        """
        import sys
        __import__(modname)
        module = sys.modules[modname]
        self.set_from_dict(vars(module), source=module.__file__)

    def read_defaults(self):
        self.read_from_module("quixote.config")

# class Config
