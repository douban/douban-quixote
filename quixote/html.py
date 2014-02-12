"""Various functions for dealing with HTML.
$HeadURL: svn+ssh://svn/repos/trunk/quixote/html.py $
$Id$

These functions are fairly simple but it is critical that they be
used correctly.  Many security problems are caused by quoting errors
(cross site scripting is one example).  The HTML and XML standards on
www.w3c.org and www.xml.com should be studied, especially the sections
on character sets, entities, attribute and values.

htmltext and htmlescape
-----------------------

This type and function are meant to be used with [html] PTL template type.
The htmltext type designates data that does not need to be escaped and the
htmlescape() function calls str() on the argment, escapes the resulting
string and returns a htmltext instance.  htmlescape() does nothing to
htmltext instances.


html_quote
----------

Use for quoting data that will be used within attribute values or as
element contents (if the [html] template type is not being used).
Examples:

    '<title>%s</title>' % html_quote(title)
    '<input type="hidden" value="%s" />' % html_quote(data)
    '<a href="%s">something</a>' % html_quote(url)

Note that the \" character should be used to surround attribute values.


url_quote
---------

Use for quoting data to be included as part of a URL, for example:

    input = "foo bar"
    ...
    '<a href="/search?keyword=%s">' % url_quote(input)

Note that URLs are usually used as attribute values and should be quoted
using html_quote.  For example:

    url = 'http://example.com/?a=1&copy=0'
    ...
    '<a href="%s">do something</a>' % html_quote(url)

If html_quote is not used, old browsers would treat "&copy" as an entity
reference and replace it with the copyright character.  XML processors should
treat it as an invalid entity reference.

"""

__revision__ = "$Id$"

import urllib
from types import UnicodeType

try:
    # faster C implementation
    from quixote._c_htmltext import htmltext, htmlescape, _escape_string, \
        TemplateIO
except ImportError:
    from quixote._py_htmltext import htmltext, htmlescape, _escape_string, \
        TemplateIO

ValuelessAttr = ["valueless_attr"] # magic singleton object

def htmltag(tag, xml_end=0, css_class=None, **attrs):
    """Create a HTML tag.
    """
    r = ["<%s" % tag]
    if css_class is not None:
        attrs['class'] = css_class
    for (attr, val) in attrs.items():
        if val is ValuelessAttr:
            val = attr
        if val is not None:
            r.append(' %s="%s"' % (attr, _escape_string(str(val))))
    if xml_end:
        r.append(" />")
    else:
        r.append(">")
    return htmltext("".join(r))


def href(url, text, title=None, **attrs):
    return (htmltag("a", href=url, title=title, **attrs) +
            htmlescape(text) +
            htmltext("</a>"))


def nl2br(value):
    """nl2br(value : any) -> htmltext

    Insert <br /> tags before newline characters.
    """
    text = htmlescape(value)
    return htmltext(text.s.replace('\n', '<br />\n'))


def url_quote(value, fallback=None):
    """url_quote(value : any [, fallback : string]) -> string

    Quotes 'value' for use in a URL; see urllib.quote().  If value is None,
    then the behavior depends on the fallback argument.  If it is not
    supplied then an error is raised.  Otherwise, the fallback value is
    returned unquoted.
    """
    if value is None:
        if fallback is None:
            raise ValueError, "value is None and no fallback supplied"
        else:
            return fallback
    if isinstance(value,  UnicodeType):
        value = value.encode('iso-8859-1')
    else:
        value = str(value)
    return urllib.quote(value)


#
# The rest of this module is for Quixote applications that were written
# before 'htmltext'.  If you are writing a new application, ignore them.
#

def html_quote(value, fallback=None):
    """html_quote(value : any [, fallback : string]) -> str

    Quotes 'value' for use in an HTML page.  The special characters &,
    <, > are replaced by SGML entities.  If value is None, then the
    behavior depends on the fallback argument.  If it is not supplied
    then an error is raised.  Otherwise, the fallback value is returned
    unquoted.
    """
    if value is None:
        if fallback is None:
            raise ValueError, "value is None and no fallback supplied"
        else:
            return fallback
    elif isinstance(value,  UnicodeType):
        value = value.encode('iso-8859-1')
    else:
        value = str(value)
    value = value.replace("&", "&amp;") # must be done first
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    return value


def value_quote(value):
    """Quote HTML attribute values.  This function is of marginal
    utility since html_quote can be used.

    XHTML 1.0 requires that all values be quoted.  weblint claims
    that some clients don't understand single quotes.  For compatibility
    with HTML, XHTML 1.0 requires that ampersands be encoded.
    """
    assert value is not None, "can't pass None to value_quote"
    value = str(value).replace('&', '&amp;')
    value = value.replace('"', '&quot;')
    return '"%s"' % value


def link(url, text, title=None, name=None, **kwargs):
    return render_tag("a", href=url, title=title, name=name,
                      **kwargs) + str(text) + "</a>"


def render_tag(tag, xml_end=0, **attrs):
    r = "<%s" % tag
    for (attr, val) in attrs.items():
        if val is ValuelessAttr:
            r += ' %s="%s"' % (attr, attr)
        elif val is not None:
            r += " %s=%s" % (attr, value_quote(val))
    if xml_end:
        r += " />"
    else:
        r += ">"
    return r
