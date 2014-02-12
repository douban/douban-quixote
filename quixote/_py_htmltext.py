"""Python implementation of the htmltext type, the htmlescape function and
TemplateIO.
"""

#$HeadURL: svn+ssh://svn/repos/trunk/quixote/_py_htmltext.py $
#$Id$

import sys
from types import UnicodeType, TupleType, StringType, IntType, FloatType, \
    LongType
import re

if sys.hexversion < 0x20200b1:
    # 2.2 compatibility hacks
    class object:
        pass

    def classof(o):
        if hasattr(o, "__class__"):
            return o.__class__
        else:
            return type(o)

else:
    classof = type

_format_codes = 'diouxXeEfFgGcrs%'
_format_re = re.compile(r'%%[^%s]*[%s]' % (_format_codes, _format_codes))

def _escape_string(s):
    if not isinstance(s, StringType):
        raise TypeError, 'string required'
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    return s

class htmltext(object):
    """The htmltext string-like type.  This type serves as a tag
    signifying that HTML special characters do not need to be escaped
    using entities.
    """

    __slots__ = ['s']

    def __init__(self, s):
        self.s = str(s)

    # XXX make read-only
    #def __setattr__(self, name, value):
    #    raise AttributeError, 'immutable object'

    def __getstate__(self):
        raise ValueError, 'htmltext objects should not be pickled'

    def __repr__(self):
        return '<htmltext %r>' % self.s

    def __str__(self):
        return self.s

    def __len__(self):
        return len(self.s)

    def __cmp__(self, other):
        return cmp(self.s, other)

    def __hash__(self):
        return hash(self.s)

    def __mod__(self, args):
        codes = []
        usedict = 0
        for format in _format_re.findall(self.s):
            if format[-1] != '%':
                if format[1] == '(':
                    usedict = 1
                codes.append(format[-1])
        if usedict:
            args = _DictWrapper(args)
        else:
            if len(codes) == 1 and not isinstance(args, TupleType):
                args = (args,)
            args = tuple([_wraparg(arg) for arg in args])
        return self.__class__(self.s % args)

    def __add__(self, other):
        if isinstance(other, StringType):
            return self.__class__(self.s + _escape_string(other))
        elif classof(other) is self.__class__:
            return self.__class__(self.s + other.s)
        else:
            return NotImplemented

    def __radd__(self, other):
        if isinstance(other, StringType):
            return self.__class__(_escape_string(other) + self.s)
        else:
            return NotImplemented

    def __mul__(self, n):
        return self.__class__(self.s * n)

    def join(self, items):
        quoted_items = []
        for item in items:
            if classof(item) is self.__class__:
                quoted_items.append(str(item))
            elif isinstance(item, StringType):
                quoted_items.append(_escape_string(item))
            else:
                raise TypeError(
                    'join() requires string arguments (got %r)' % item)
        return self.__class__(self.s.join(quoted_items))

    def startswith(self, s):
        if isinstance(s, htmltext):
            s = s.s
        else:
            s = _escape_string(s)
        return self.s.startswith(s)

    def endswith(self, s):
        if isinstance(s, htmltext):
            s = s.s
        else:
            s = _escape_string(s)
        return self.s.endswith(s)

    def replace(self, old, new, maxsplit=-1):
        if isinstance(old, htmltext):
            old = old.s
        else:
            old = _escape_string(old)
        if isinstance(new, htmltext):
            new = new.s
        else:
            new = _escape_string(new)
        return self.__class__(self.s.replace(old, new))

    def lower(self):
        return self.__class__(self.s.lower())

    def upper(self):
        return self.__class__(self.s.upper())

    def capitalize(self):
        return self.__class__(self.s.capitalize())

class _QuoteWrapper(object):
    # helper for htmltext class __mod__

    __slots__ = ['value', 'escape']

    def __init__(self, value, escape):
        self.value = value
        self.escape = escape

    def __str__(self):
        return self.escape(str(self.value))

    def __repr__(self):
        return self.escape(`self.value`)

class _DictWrapper(object):
    def __init__(self, value):
        self.value = value

    def __getitem__(self, key):
        return _wraparg(self.value[key])

def _wraparg(arg):
    if (classof(arg) is htmltext or
        isinstance(arg, IntType) or
        isinstance(arg, LongType) or
        isinstance(arg, FloatType)):
        # ints, longs, floats, and htmltext are okay
        return arg
    else:
        # everything is gets wrapped
        return _QuoteWrapper(arg, _escape_string)

def htmlescape(s):
    """htmlescape(s) -> htmltext

    Return an 'htmltext' object using the argument.  If the argument is not
    already a 'htmltext' object then the HTML markup characters \", <, >,
    and & are first escaped.
    """
    if classof(s) is htmltext:
        return s
    elif isinstance(s,  UnicodeType):
        s = s.encode('iso-8859-1')
    else:
        s = str(s)
    # inline _escape_string for speed
    s = s.replace("&", "&amp;") # must be done first
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    return htmltext(s)


class TemplateIO(object):
    """Collect output for PTL scripts.
    """

    __slots__ = ['html', 'data']

    def __init__(self, html=0):
        self.html = html
        self.data = []

    def __iadd__(self, other):
        if other is not None:
            self.data.append(other)
        return self

    def __repr__(self):
        return ("<%s at %x: %d chunks>" %
                (self.__class__.__name__, id(self), len(self.data)))

    def __str__(self):
        return str(self.getvalue())

    def getvalue(self):
        if self.html:
            return htmltext('').join(map(htmlescape, self.data))
        else:
            return ''.join(map(str, self.data))
