"""quixote.http_request
$HeadURL: svn+ssh://svn/repos/trunk/quixote/http_request.py $
$Id$

Provides the HTTPRequest class and related code for parsing HTTP
requests, such as the FileUpload class.

Derived from Zope's HTTPRequest module (hence the different
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

import re
import time
import urlparse, urllib
from cgi import FieldStorage
from types import ListType

from quixote import errors
from quixote.http_response import HTTPResponse
from quixote.html import html_quote
from quixote.util import filter_input, convert_unicode_to_utf8_in_json
from json import loads


# Various regexes for parsing specific bits of HTTP, all from RFC 2616.

# These are needed by 'get_encoding()', to parse the "Accept-Encoding"
# header.  LWS is linear whitespace; the latter two assume that LWS
# has been removed.
_http_lws_re = re.compile("(\r\n)?[ \t]+")
_http_list_re = re.compile(r",+")
_http_encoding_re = re.compile(r"([^;]+)(;q=([\d.]+))?$")

#redirect filter \r\n
_http_redir_re = re.compile("[\r\n]+")

# These are needed by 'guess_browser_version()', for parsing the
# "User-Agent" header.
#   token = 1*<any CHAR except CTLs or separators>
#   CHAR = any 7-bit US ASCII character (0-127)
#   separators are  ( ) < > @ , ; : \ " / [ ] ? = { }
#
# The user_agent RE is a simplification; it only looks for one "product",
# possibly followed by a comment.
_http_token_pat = r'[^\x00-\x20\(\)\<\>\@\,\;\:\\\"\/\[\]\?\=\{\}\x7F-\xFF]+'
_http_product_pat = r'(%s)(?:/(%s))?' % (_http_token_pat, _http_token_pat)
_http_product_re = re.compile(_http_product_pat)
_comment_delim_re = re.compile(r';\s*')


def get_content_type(environ):
    ctype = environ.get("CONTENT_TYPE")
    if ctype:
        return ctype.split(";")[0]
    else:
        return None


class HTTPRequest:
    """
    Model a single HTTP request and all associated data: environment
    variables, form variables, cookies, etc.

    To access environment variables associated with the request, use
    get_environ(): eg. request.get_environ('SERVER_PORT', 80).

    To access form variables, use get_form_var(), eg.
    request.get_form_var("name").

    To access cookies, use get_cookie().

    Various bits and pieces of the requested URL can be accessed with
    get_url(), get_path(), get_server()

    The HTTPResponse object corresponding to this request is available
    in the 'response' attribute.  This is rarely needed: eg. to send an
    error response, you should raise one of the exceptions in errors.py;
    to send a redirect, you should use the request's redirect() method,
    which lets you specify relative URLs.  However, if you need to tweak
    the response object in other ways, you can do so via 'response'.
    Just keep in mind that Quixote discards the original response object
    when handling an exception.
    """

    def __init__(self, stdin, environ, content_type=None):
        self.stdin = stdin
        self.environ = environ
        if content_type is None:
            self.content_type = get_content_type(environ)
        else:
            self.content_type = content_type
        self.form = {}
        self.session = None
        self.response = HTTPResponse()
        self.start_time = None

        # The strange treatment of SERVER_PORT_SECURE is because IIS
        # sets this environment variable to "0" for non-SSL requests
        # (most web servers -- well, Apache at least -- simply don't set
        # it in that case).
        if (environ.get('HTTPS', 'off').lower() == 'on' or
            environ.get('SERVER_PORT_SECURE', '0') != '0' or
            environ.get('HTTP_X_FORWARDED_PROTO', 'http') == 'https'):
            self.scheme = "https"
        else:
            self.scheme = "http"

        k = self.environ.get('HTTP_COOKIE', '')
        if k:
            self.cookies = parse_cookie(k)
        else:
            self.cookies = {}

        # IIS breaks PATH_INFO because it leaves in the path to
        # the script, so SCRIPT_NAME is "/cgi-bin/q.py" and PATH_INFO
        # is "/cgi-bin/q.py/foo/bar".  The following code fixes
        # PATH_INFO to the expected value "/foo/bar".
        web_server = environ.get('SERVER_SOFTWARE', 'unknown')
        if web_server.find('Microsoft-IIS') != -1:
            script = environ['SCRIPT_NAME']
            path = environ['PATH_INFO']
            if path.startswith(script):
                path = path[len(script):]
                self.environ['PATH_INFO'] = path

    def add_form_value(self, key, value):
        if self.form.has_key(key):
            found = self.form[key]
            if type(found) is ListType:
                found.append(value)
            else:
                found = [found, value]
                self.form[key] = found
        else:
            self.form[key] = value
            # anti hash attack:
            # http://permalink.gmane.org/gmane.comp.security.full-disclosure/83694
            n = len(self.form)
            if n % 100 == 0:
                hash_d = {}
                for k in self.form:
                    h = hash(k)
                    hash_d[h] = hash_d.get(h, 0) + 1
                m = max(hash_d.values())
                if m > n / 10 or m > 100 or len(hash_d) < n/3 or n > 50000:
                    raise errors.RequestError("hash attack")

    def process_inputs(self):
        """Process request inputs.
        """
        self.start_time = time.time()
        if self.get_method() != 'GET':
            # Avoid consuming the contents of stdin unless we're sure
            # there's actually form data.
            if self.content_type == "multipart/form-data":
                raise RuntimeError(
                    "cannot handle multipart/form-data requests")
            elif self.content_type == "application/x-www-form-urlencoded":
                fp = self.stdin
            else:
                return
        else:
            fp = None

        fs = FieldStorage(fp=fp, environ=self.environ, keep_blank_values=1)
        if fs.list:
            for item in fs.list:
                self.add_form_value(item.name, item.value)

    def get_header(self, name, default=None):
        """get_header(name : string, default : string = None) -> string

        Return the named HTTP header, or an optional default argument
        (or None) if the header is not found.  Note that both original
        and CGI-ified header names are recognized, e.g. 'Content-Type',
        'CONTENT_TYPE' and 'HTTP_CONTENT_TYPE' should all return the
        Content-Type header, if available.
        """
        environ = self.environ
        name = name.replace("-", "_").upper()
        val = environ.get(name)
        if val is not None:
            return val
        if name[:5] != 'HTTP_':
            name = 'HTTP_' + name
        return environ.get(name, default)

    def get_cookie(self, cookie_name, default=None):
        return self.cookies.get(cookie_name, default)

    def _get_form_var(self, var_name, default=None):
        var = self.form.get(var_name, default)
        if var and self.get_method() == 'POST' and isinstance(var, basestring):
            var = filter_input(var)
        return var

    def get_form_var(self, var_name, default=None):
        var = self._get_form_var(var_name, default)
        if type(var) is ListType and len(set(var)) == 1:
            var = var[0]
        return var

    def get_form_list_var(self, var_name, default=[]):
        var = self._get_form_var(var_name, default)
        if type(var) is not ListType:
            var = [var]
        return var

    def get_method(self):
        """Returns the HTTP method for this request
        """
        return self.environ.get('REQUEST_METHOD', 'GET')

    def formiter(self):
        return self.form.iteritems()

    def get_scheme(self):
        return self.scheme

    # The following environment variables are useful for reconstructing
    # the original URL, all of which are specified by CGI 1.1:
    #
    #   SERVER_NAME            "www.example.com"
    #   SCRIPT_NAME            "/q"
    #   PATH_INFO              "/debug/dump_sessions"
    #   QUERY_STRING           "session_id=10.27.8.40...."

    def get_server(self):
        """get_server() -> string

        Return the server name with an optional port number, eg.
        "www.example.com" or "foo.bar.com:8000".
        """
        http_host = self.environ.get("HTTP_HOST")
        if http_host:
            return http_host
        server_name = self.environ["SERVER_NAME"].strip()
        server_port = self.environ.get("SERVER_PORT")
        if (not server_port or
            (self.get_scheme() == "http" and server_port == "80") or
            (self.get_scheme() == "https" and server_port == "443")):
            return server_name
        else:
            return server_name + ":" + server_port

    def get_path(self, n=0):
        """get_path(n : int = 0) -> string

        Return the path of the current request, chopping off 'n' path
        components from the right.  Eg. if the path is "/bar/baz/qux",
        n=0 would return "/bar/baz/qux" and n=2 would return "/bar".
        Note that the query string, if any, is not included.

        A path with a trailing slash should just be considered as having
        an empty last component.  Eg. if the path is "/bar/baz/", then:
          get_path(0) == "/bar/baz/"
          get_path(1) == "/bar/baz"
          get_path(2) == "/bar"

        If 'n' is negative, then components from the left of the path
        are returned.  Continuing the above example,
          get_path(-1) = "/bar"
          get_path(-2) = "/bar/baz"
          get_path(-3) = "/bar/baz/"

        Raises ValueError if absolute value of n is larger than the number of
        path components."""

        path_info = self.environ.get('PATH_INFO', '')
        path = self.environ['SCRIPT_NAME'] + path_info
        if n == 0:
            return path
        else:
            path_comps = path.split('/')
            if abs(n) > len(path_comps)-1:
                raise ValueError, "n=%d too big for path '%s'" % (n, path)
            if n > 0:
                return '/'.join(path_comps[:-n])
            elif n < 0:
                return '/'.join(path_comps[:-n+1])
            else:
                assert 0, "Unexpected value for n (%s)" % n

    def get_url(self, n=0):
        """get_url(n : int = 0) -> string

        Return the URL of the current request, chopping off 'n' path
        components from the right.  Eg. if the URL is
        "http://foo.com/bar/baz/qux", n=2 would return
        "http://foo.com/bar".  Does not include the query string (if
        any).
        """
        return "%s://%s%s" % (self.get_scheme(), self.get_server(),
                              urllib.quote(self.get_path(n)))

    def get_environ(self, key, default=None):
        """get_environ(key : string) -> string

        Fetch a CGI environment variable from the request environment.
        See http://hoohoo.ncsa.uiuc.edu/cgi/env.html
        for the variables specified by the CGI standard.
        """
        return self.environ.get(key, default)

    def get_encoding(self, encodings):
        """get_encoding(encodings : [string]) -> string

        Parse the "Accept-encoding" header. 'encodings' is a list of
        encodings supported by the server sorted in order of preference.
        The return value is one of 'encodings' or None if the client
        does not accept any of the encodings.
        """
        accept_encoding = self.get_header("accept-encoding") or ""
        found_encodings = self._parse_pref_header(accept_encoding)
        if found_encodings:
            for encoding in encodings:
                if found_encodings.has_key(encoding):
                    return encoding
        return None

    def get_accepted_types(self):
        """get_accepted_types() : {string:float}
        Return a dictionary mapping MIME types the client will accept
        to the corresponding quality value (1.0 if no value was specified).
        """
        accept_types = self.environ.get('HTTP_ACCEPT', "")
        return self._parse_pref_header(accept_types)


    def _parse_pref_header(self, S):
        """_parse_pref_header(S:string) : {string:float}
        Parse a list of HTTP preferences (content types, encodings) and
        return a dictionary mapping strings to the quality value.
        """

        found = {}
        # remove all linear whitespace
        S = _http_lws_re.sub("", S)
        for coding in _http_list_re.split(S):
            m = _http_encoding_re.match(coding)
            if m:
                encoding = m.group(1).lower()
                q = m.group(3) or 1.0
                try:
                    q = float(q)
                except ValueError:
                    continue
                if encoding == "*":
                    continue # stupid, ignore it
                if q > 0:
                    found[encoding] = q
        return found


    def dump_html(self):
        row_fmt=('<tr valign="top"><th align="left">%s</th><td>%s</td></tr>')
        lines = ["<h3>form</h3>",
                 "<table>"]

        for k,v in self.form.items():
            lines.append(row_fmt % (html_quote(k), html_quote(v)))
        lines += ["</table>",
                  "<h3>cookies</h3>",
                  "<table>"]
        for k,v in self.cookies.items():
            lines.append(row_fmt % (html_quote(k), html_quote(v)))

        lines += ["</table>",
                  "<h3>environ</h3>"
                  "<table>"]
        for k,v in self.environ.items():
            lines.append(row_fmt % (html_quote(k), html_quote(str(v))))
        lines.append("</table>")

        return "\n".join(lines)

    def dump(self):
        result=[]
        row='%-15s %s'

        result.append("Form:")
        L = self.form.items() ; L.sort()
        for k,v in L:
            result.append(row % (k,v))

        result.append("")
        result.append("Cookies:")
        L = self.cookies.items() ; L.sort()
        for k,v in L:
            result.append(row % (k,v))


        result.append("")
        result.append("Environment:")
        L = self.environ.items() ; L.sort()
        for k,v in L:
            result.append(row % (k,v))
        return "\n".join(result)

    def guess_browser_version(self):
        """guess_browser_version() -> (name : string, version : string)

        Examine the User-agent request header to try to figure out what
        the current browser is.  Returns either (name, version) where
        each element is a string, (None, None) if we couldn't parse the
        User-agent header at all, or (name, None) if we got the name but
        couldn't figure out the version.

        Handles Microsoft's little joke of pretending to be Mozilla,
        eg. if the "User-Agent" header is
          Mozilla/5.0 (compatible; MSIE 5.5)
        returns ("MSIE", "5.5").  Konqueror does the same thing, and
        it's handled the same way.
        """
        ua = self.get_header('user-agent')
        if ua is None:
            return (None, None)

        # The syntax for "User-Agent" in RFC 2616 is fairly simple:
        #
        #  User-Agent      = "User-Agent" ":" 1*( product | comment )
        #  product         = token ["/" product-version ]
        #  product-version = token
        #  comment         = "(" *( ctext | comment ) ")"
        #  ctext           = <any TEXT excluding "(" and ")">
        #  token           = 1*<any CHAR except CTLs or tspecials>
        #  tspecials       = "(" | ")" | "<" | ">" | "@" | "," | ";" | ":" |
        #                    "\" | <"> | "/" | "[" | "]" | "?" | "=" | "{" |
        #                    "}" | SP | HT
        #
        # This function handles the most-commonly-used subset of this syntax,
        # namely
        #   User-Agent = "User-Agent" ":" product 1*SP [comment]
        # ie. one product string followed by an optional comment;
        # anything after that first comment is ignored.  This should be
        # enough to distinguish Mozilla/Netscape, MSIE, Opera, and
        # Konqueror.

        m = _http_product_re.search(ua)
        if not m:
            if ua:
                import sys
                sys.stderr.write("couldn't parse User-Agent header: %r\n" % ua)
            return (None, None)

        name, version = m.groups()
        ua = ua[m.end():].lstrip()

        if ua.startswith('('):
            # we need to handle nested comments since MSIE uses them
            depth = 1
            chars = []
            for c in ua[1:]:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        break
                elif depth == 1:
                    # nested comments are discarded
                    chars.append(c)
            comment = ''.join(chars)
        else:
            comment = ''
        if comment:
            comment_chunks = _comment_delim_re.split(comment)
        else:
            comment_chunks = []

        if ("compatible" in comment_chunks and
            len(comment_chunks) > 1 and comment_chunks[1]):
            # A-ha!  Someone is kidding around, pretending to be what
            # they are not.  Most likely MSIE masquerading as Mozilla,
            # but lots of other clients (eg. Konqueror) do the same.
            real_ua = comment_chunks[1]
            if "/" in real_ua:
                (name, version) = real_ua.split("/", 1)
            else:
                if real_ua.startswith("MSIE") and ' ' in real_ua:
                    (name, version) = real_ua.split(" ", 1)
                else:
                    name = real_ua
                    version = None
            return (name, version)

        # Either nobody is pulling our leg, or we didn't find anything
        # that looks vaguely like a user agent in the comment.  So use
        # what we found outside the comment, ie. what the spec says we
        # should use (sigh).
        return (name, version)

    # guess_browser_version ()

    def redirect(self, location, permanent=0):
        """redirect(location : string, permanent : boolean = false)
           -> string

        Create a redirection response.  If the location is relative, then it
        will automatically be made absolute.  The return value is an HTML
        document indicating the new URL (useful if the client browser does
        not honor the redirect).
        """
        location = urlparse.urljoin(self.get_url(), location)
        location = _http_redir_re.sub('', location)
        return self.response.redirect(location, permanent)


class HTTPJSONRequest(HTTPRequest):
    def process_inputs(self):
        self.start_time = time.time()
        if self.content_type != "application/json":
            return

        try:
            length = int(self.environ["CONTENT_LENGTH"])
            raw_json = self.stdin.read(length)
            # Since object_hook/object_pairs_hook is only for JSON object, direct convertion on return value is prefered
            json = convert_unicode_to_utf8_in_json(loads(raw_json))
        except ValueError:
            raise errors.QueryError

        self.json = json

        if type(self.json) is dict:
            for k, v in self.json.iteritems():
                self.add_form_value(k, v)


_qparm_re = re.compile(r'([\0- ]*'
                       r'([^\0- ;,=\"]+)="([^"]*)"'
                       r'([\0- ]*[;,])?[\0- ]*)')
_parm_re = re.compile(r'([\0- ]*'
                      r'([^\0- ;,="]+)=([^\0- ;"]*)'
                      r'([\0- ]*[;,])?[\0- ]*)')

def parse_cookie(text):
    result = {}

    pos = 0
    while pos < len(text):
        mq = _qparm_re.match(text, pos)
        m = _parm_re.match(text, pos)
        if mq is not None:
            # Match quoted correct cookies
            name = mq.group(2)
            value = mq.group(3)
            pos = mq.end()
        elif m is not None:
            # Match evil MSIE cookies ;)
            name = m.group(2)
            value = m.group(3)
            pos = m.end()
        elif text.find(";", pos) >= 0:
            # skip the heading ";"
            pos = text.index(";", pos) + 1
            continue
        else:
            # this may be an invalid cookie.
            # We'll simply bail without raising an error
            # if the cookie is invalid.
            return result

        if not result.has_key(name):
            result[name] = value

    return result
