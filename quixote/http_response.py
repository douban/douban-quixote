"""quixote.http_response
$HeadURL: svn+ssh://svn/repos/trunk/quixote/http_response.py $
$Id$

Provides the HTTPResponse class.

Derived from Zope's HTTPResponse module (hence the different
copyright and license from the rest of Quixote).
"""

##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

__revision__ = "$Id$"

import time
from rfc822 import formatdate
from types import StringType, IntType

status_reasons = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi-Status',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Moved Temporarily',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Time-out',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Large',
    415: 'Unsupported Media Type',
    416: 'Requested range not satisfiable',
    417: 'Expectation Failed',
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Time-out',
    505: 'HTTP Version not supported',
    507: 'Insufficient Storage',
}


class HTTPResponse:
    """
    An object representation of an HTTP response.

    The Response type encapsulates all possible responses to HTTP
    requests.  Responses are normally created by the Quixote publisher
    or by the HTTPRequest class (every request must have a response,
    after all).

    Instance attributes:
      status_code : int
        HTTP response status code (integer between 100 and 599)
      reason_phrase : string
        the reason phrase that accompanies status_code (usually
        set automatically by the set_status() method)
      headers : { string : string }
        most of the headers included with the response; every header set
        by 'set_header()' goes here.  Does not include "Status" or
        "Set-Cookie" headers (unless someone uses set_header() to set
        them, but that would be foolish).
      body : string
        the response body, None by default.  If the body is never
        set (ie. left as None), the response will not include
        "Content-type" or "Content-length" headers.  These headers
        are set as soon as the body is set (with set_body()), even
        if the body is an empty string.
      buffered : bool
        if false, response data will be flushed as soon as it is
        written (the default is true).  This is most useful for
        responses that use the Stream() protocol.  Note that whether the
        client actually receives the partial response data is highly
        dependent on the web server
      cookies : { name:string : { attrname : value } }
        collection of cookies to set in this response; it is expected
        that the user-agent will remember the cookies and send them on
        future requests.  The cookie value is stored as the "value"
        attribute.  The other attributes are as specified by RFC 2109.
      cache : int | None
        the number of seconds the response may be cached.  The default is 0,
        meaning don't cache at all.  This variable is used to set the HTTP
        expires header.  If set to None then the expires header will not be
        added.
      javascript_code : { string : string }
        a collection of snippets of JavaScript code to be included in
        the response.  The collection is built by calling add_javascript(),
        but actually including the code in the HTML document is somebody
        else's problem.
    """

    def __init__(self, status=200, body=None):
        """
        Creates a new HTTP response.
        """
        self.set_status(status)
        self.headers = {}

        if body is not None:
            self.set_body(body)
        else:
            self.body = None

        self.cookies = {}
        self.cache = 0
        self.buffered = 1
        self.javascript_code = None

    def set_status(self, status, reason=None):
        """set_status(status : int, reason : string = None)

        Sets the HTTP status code of the response.  'status' must be an
        integer in the range 100 .. 599.  'reason' must be a string; if
        not supplied, the default reason phrase for 'status' will be
        used.  If 'status' is a non-standard status code, the generic
        reason phrase for its group of status codes will be used; eg.
        if status == 493, the reason for status 400 will be used.
        """
        if type(status) is not IntType:
            raise TypeError, "status must be an integer"
        if not (100 <= status <= 599):
            raise ValueError, "status must be between 100 and 599"

        self.status_code = status
        if reason is None:
            if status_reasons.has_key(status):
                reason = status_reasons[status]
            else:
                # Eg. for generic 4xx failures, use the reason
                # associated with status 400.
                reason = status_reasons[status - (status % 100)]
        else:
            reason = str(reason)

        self.reason_phrase = reason

    def set_header(self, name, value):
        """set_header(name : string, value : string)

        Sets an HTTP return header "name" with value "value", clearing
        the previous value set for the header, if one exists.
        """
        self.headers[name.lower()] = value

    def get_header(self, name, default=None):
        """get_header(name : string, default=None) -> value : string

        Gets an HTTP return header "name".  If none exists then 'default' is
        returned.
        """
        return self.headers.get(name.lower(), default)

    def set_content_type(self, ctype):
        """set_content_type(ctype : string)

        Set the "Content-type" header to the MIME type specified in ctype.
        Shortcut for set_header("Content-type", ctype).
        """
        self.headers["content-type"] = ctype

    def set_body(self, body):
        """set_body(body : any)

        Sets the return body equal to the argument "body". Also updates the
        "Content-length" header if the length is of the body is known.  If
        the "Content-type" header has not yet been set, it is set to
        "text/html".
        """
        if isinstance(body, Stream):
            self.body = body
            if body.length is not None:
                self.set_header('content-length', body.length)
        else:
            self.body = str(body)
            self.set_header('content-length', len(self.body))
        if not self.headers.has_key('content-type'):
            self.set_header('content-type', 'text/html; charset=iso-8859-1')

    def expire_cookie(self, name, **attrs):
        """
        Cause an HTTP cookie to be removed from the browser

        The response will include an HTTP header that will remove the cookie
        corresponding to "name" on the client, if one exists.  This is
        accomplished by sending a new cookie with an expiration date
        that has already passed.  Note that some clients require a path
        to be specified - this path must exactly match the path given
        when creating the cookie.  The path can be specified as a keyword
        argument.
        """
        dict = {'max_age': 0, 'expires': 'Thu, 01-Jan-1970 00:00:00 GMT'}
        dict.update(attrs)
        self.set_cookie(name, "deleted", **dict)

    def set_cookie(self, name, value, **attrs):
        """set_cookie(name : string, value : string, **attrs)

        Set an HTTP cookie on the browser.

        The response will include an HTTP header that sets a cookie on
        cookie-enabled browsers with a key "name" and value "value".
        Cookie attributes such as "expires" and "domains" may be
        supplied as keyword arguments; see RFC 2109 for a full list.
        (For the "secure" attribute, use any true value.)

        This overrides any previous value for this cookie.  Any
        previously-set attributes for the cookie are preserved, unless
        they are explicitly overridden with keyword arguments to this
        call.
        """
        cookies = self.cookies
        if cookies.has_key(name):
            cookie = cookies[name]
        else:
            cookie = cookies[name] = {}
        cookie.update(attrs)
        cookie['value'] = value

    def add_javascript(self, code_id, code):
        """Add javascript code to be included in the response.

        code_id is used to ensure that the same piece of code is not
        included twice.  The caller must be careful to avoid
        unintentional code_id and javascript identifier collisions.
        Note that the response object only provides a mechanism for
        collecting code -- actually including it in the HTML document
        that is the response body is somebody else's problem.  (For
        an example, see Form._render_javascript().)
        """
        if self.javascript_code is None:
            self.javascript_code = {code_id: code}
        elif not self.javascript_code.has_key(code_id):
            self.javascript_code[code_id] = code

    def redirect(self, location, permanent=0):
        """Cause a redirection without raising an error"""
        if not isinstance(location, StringType):
            raise TypeError, "location must be a string (got %s)" % `location`
        # Ensure that location is a full URL
        if location.find('://') == -1:
            raise ValueError, "URL must include the server name"
        if permanent:
            status = 301
        else:
            status = 302
        self.set_status(status)
        self.headers['location'] = location
        self.set_content_type('text/plain')
        return "Your browser should have redirected you to %s" % location

    def _gen_cookie_headers(self):
        """_gen_cookie_headers() -> [string]

        Build a list of "Set-Cookie" headers based on all cookies
        set with 'set_cookie()', and return that list.
        """
        cookie_list = []
        for (name, attrs) in self.cookies.items():

            # Note that as of May 98, IE4 ignores cookies with
            # quoted cookie attr values, so only the value part
            # of name=value pairs may be quoted.

            # 'chunks' is a list of "name=val" chunks; will be joined
            # with "; " to create the "Set-cookie" header.
            chunks = ['%s="%s"' % (name, attrs['value'])]

            for (name, val) in attrs.items():
                name = name.lower()
                if val is None:
                    continue
                if name in ('expires', 'domain', 'path', 'max_age', 'comment'):
                    name = name.replace('_', '-')
                    chunks.append("%s=%s" % (name, val))
                elif name == 'secure' and val:
                    chunks.append("secure")
                elif name == 'httponly' and val:
                    chunks.append("httponly")

            cookie_list.append(("Set-Cookie", ("; ".join(chunks))))

        # Should really check size of cookies here!

        return cookie_list

    def generate_headers(self):
        """generate_headers() -> [(name:string, value:string)]

        Generate a list of headers to be returned as part of the response.
        """
        headers = []

        # "Status" header must come first.
        headers.append(("Status", "%03d %s" % (self.status_code,
                                               self.reason_phrase)))

        for name, value in self.headers.items():
            headers.append((name.title(), value))

        # All the "Set-Cookie" headers.
        if self.cookies:
            headers.extend(self._gen_cookie_headers())

        # Date header
        now = time.time()
        if not self.headers.has_key("date"):
            headers.append(("Date", formatdate(now)))

        # Cache directives
        if self.cache is None:
            pass # don't mess with the expires header
        elif not self.headers.has_key("expires"):
            if self.cache > 0:
                expire_date = formatdate(now + self.cache)
            else:
                expire_date = "-1" # allowed by HTTP spec and may work better
                                   # with some clients
            headers.append(("Expires", expire_date))

        return headers


    def write(self, file):
        """write(file : file)

        Write the HTTP response headers and body to 'file'.  This is not
        a complete HTTP response, as it doesn't start with a response
        status line as specified by RFC 2616.  It does, however, start
        with a "Status" header as described by the CGI spec.  It
        is expected that this response is parsed by the web server
        and turned into a complete HTTP response.
        """
        # XXX currently we write a response like this:
        #  Status: 200 OK
        #  Content-type: text/html; charset=iso-8859-1
        #  Content-length: 100
        #  Set-Cookie: foo=bar
        #  Set-Cookie: bar=baz
        #
        #  <html><body>This is a document</body></html>
        #
        # which has to be interpreted by the web server to create
        # a true HTTP response -- that is, this is for a
        # "parsed header" CGI driver script.
        #
        # We should probably have provisions for operating in
        # "non-parsed header" mode, where the CGI script is responsible
        # for generating a complete HTTP response with no help from the
        # server.
        flush_output = not self.buffered and hasattr(file, 'flush')
        for name, value in self.generate_headers():
            file.write("%s: %s\r\n" % (name, value))
        file.write("\r\n")
        if self.body is not None:
            if isinstance(self.body, Stream):
                for chunk in self.body:
                    file.write(chunk)
                    if flush_output:
                        file.flush()
            else:
                file.write(self.body)
        if flush_output:
            file.flush()


class Stream:
    """
    A wrapper around response data that can be streamed.  The 'iterable'
    argument must support the iteration protocol.  Items returned by 'next()'
    must be strings.  Beware that exceptions raised while writing the stream
    will not be handled gracefully.

    Instance attributes:
      iterable : any
        an object that supports the iteration protocol.  The items produced
        by the stream must be strings.
      length: int | None
        the number of bytes that will be produced by the stream, None
        if it is not known.  Used to set the Content-Length header.
    """
    def __init__(self, iterable, length=None):
        self.iterable = iterable
        self.length = length

    def __iter__(self):
        return iter(self.iterable)
