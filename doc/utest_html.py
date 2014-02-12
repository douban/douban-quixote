#!/www/python/bin/python
"""
$URL: svn+ssh://svn/repos/trunk/quixote/test/utest_html.py $
$Id$
"""
from sancho.utest import UTest
from quixote import _py_htmltext

escape = htmlescape = None # so that checker does not complain

class Wrapper:
    def __init__(self, s):
        self.s = s

    def __repr__(self):
        return self.s

    def __str__(self):
        return self.s

class Broken:
    def __str__(self):
        raise RuntimeError, 'eieee'

    def __repr__(self):
        raise RuntimeError, 'eieee'

markupchars = '<>&"'
quotedchars = '&lt;&gt;&amp;&quot;'

class HTMLTest (UTest):

    def _pre(self):
        global htmltext, escape, htmlescape
        htmltext = _py_htmltext.htmltext
        escape = _py_htmltext._escape_string
        htmlescape = _py_htmltext.htmlescape

    def _post(self):
        pass


    def check_init(self):
        assert str(htmltext('foo')) == 'foo'
        assert str(htmltext(markupchars)) == markupchars
        assert str(htmltext(None)) == 'None'
        assert str(htmltext(1)) == '1'
        try:
            htmltext(Broken())
            assert 0
        except RuntimeError: pass

    def check_escape(self):
        assert htmlescape(markupchars) == quotedchars
        assert isinstance(htmlescape(markupchars), htmltext)
        assert escape(markupchars) == quotedchars
        assert isinstance(escape(markupchars), str)
        assert htmlescape(htmlescape(markupchars)) == quotedchars
        try:
            escape(1)
            assert 0
        except TypeError: pass

    def check_cmp(self):
        s = htmltext("foo")
        assert s == 'foo'
        assert s != 'bar'
        assert s == htmltext('foo')
        assert s != htmltext('bar')
        assert htmltext('1') != 1
        assert 1 != s

    def check_len(self):
        assert len(htmltext('foo')) == 3
        assert len(htmltext(markupchars)) == len(markupchars)
        assert len(htmlescape(markupchars)) == len(quotedchars)

    def check_hash(self):
        assert hash(htmltext('foo')) == hash('foo')
        assert hash(htmltext(markupchars)) == hash(markupchars)
        assert hash(htmlescape(markupchars)) == hash(quotedchars)

    def check_concat(self):
        s = htmltext("foo")
        assert s + 'bar' == "foobar"
        assert 'bar' + s == "barfoo"
        assert s + htmltext('bar') == "foobar"
        assert s + markupchars == "foo" + quotedchars
        assert isinstance(s + markupchars, htmltext)
        assert markupchars + s == quotedchars + "foo"
        assert isinstance(markupchars + s, htmltext)
        try:
            s + 1
            assert 0
        except TypeError: pass
        try:
            1 + s
            assert 0
        except TypeError: pass

    def check_repeat(self):
        s = htmltext('a')
        assert s * 3 == "aaa"
        assert isinstance(s * 3, htmltext)
        assert htmlescape(markupchars) * 3 == quotedchars * 3
        try:
            s * 'a'
            assert 0
        except TypeError: pass
        try:
            'a' * s
            assert 0
        except TypeError: pass
        try:
            s * s
            assert 0
        except TypeError: pass

    def check_format(self):
        s_fmt = htmltext('%s')
        assert s_fmt % 'foo' == "foo"
        assert isinstance(s_fmt % 'foo', htmltext)
        assert s_fmt % markupchars == quotedchars
        assert s_fmt % None == "None"
        assert htmltext('%r') % Wrapper(markupchars) == quotedchars
        assert htmltext('%s%s') % ('foo', htmltext(markupchars)) == (
            "foo" + markupchars)
        assert htmltext('%d') % 10 == "10"
        assert htmltext('%.1f') % 10 == "10.0"
        try:
            s_fmt % Broken()
            assert 0
        except RuntimeError: pass
        try:
            htmltext('%r') % Broken()
            assert 0
        except RuntimeError: pass
        try:
            s_fmt % (1, 2)
            assert 0
        except TypeError: pass
        assert htmltext('%d') % 12300000000000000000L == "12300000000000000000"

    def check_dict_format(self):
        assert htmltext('%(a)s %(a)r %(b)s') % (
            {'a': 'foo&', 'b': htmltext('bar&')}) == "foo&amp; 'foo&amp;' bar&"
        assert htmltext('%(a)s') % {'a': 'foo&'} == "foo&amp;"
        assert isinstance(htmltext('%(a)s') % {'a': 'a'}, htmltext)
        assert htmltext('%s') % {'a': 'foo&'} == "{'a': 'foo&amp;'}"
        try:
            htmltext('%(a)s') % 1
            assert 0
        except TypeError: pass
        try:
            htmltext('%(a)s') % {}
            assert 0
        except KeyError: pass

    def check_join(self):
        assert htmltext(' ').join(['foo', 'bar']) == "foo bar"
        assert htmltext(' ').join(['foo', markupchars]) == (
            "foo " + quotedchars)
        assert htmlescape(markupchars).join(['foo', 'bar']) == (
            "foo" + quotedchars + "bar")
        assert htmltext(' ').join([htmltext(markupchars), 'bar']) == (
            markupchars + " bar")
        assert isinstance(htmltext('').join([]), htmltext)
        try:
            htmltext('').join(1)
            assert 0
        except TypeError: pass
        try:
            htmltext('').join([1])
            assert 0
        except TypeError: pass

    def check_startswith(self):
        assert htmltext('foo').startswith('fo')
        assert htmlescape(markupchars).startswith(markupchars[:3])
        assert htmltext(markupchars).startswith(htmltext(markupchars[:3]))
        try:
            htmltext('').startswith(1)
            assert 0
        except TypeError: pass

    def check_endswith(self):
        assert htmltext('foo').endswith('oo')
        assert htmlescape(markupchars).endswith(markupchars[-3:])
        assert htmltext(markupchars).endswith(htmltext(markupchars[-3:]))
        try:
            htmltext('').endswith(1)
            assert 0
        except TypeError: pass

    def check_replace(self):
        assert htmlescape('&').replace('&', 'foo') == "foo"
        assert htmltext('&').replace(htmltext('&'), 'foo') == "foo"
        assert htmltext('foo').replace('foo', htmltext('&')) == "&"
        assert isinstance(htmltext('a').replace('a', 'b'), htmltext)
        try:
            htmltext('').replace(1, 'a')
            assert 0
        except TypeError: pass

    def check_lower(self):
        assert htmltext('aB').lower() == "ab"
        assert isinstance(htmltext('a').lower(), htmltext)

    def check_upper(self):
        assert htmltext('aB').upper() == "AB"
        assert isinstance(htmltext('a').upper(), htmltext)

    def check_capitalize(self):
        assert htmltext('aB').capitalize() == "Ab"
        assert isinstance(htmltext('a').capitalize(), htmltext)


try:
    from quixote import _c_htmltext
except ImportError:
    _c_htmltext = None

if _c_htmltext:
    class CHTMLTest(HTMLTest):
        def _pre(self):
            # using globals like this is a bit of a hack since it assumes
            # Sancho tests each class individually, oh well
            global htmltext, escape, htmlescape
            htmltext = _c_htmltext.htmltext
            escape = _c_htmltext._escape_string
            htmlescape = _c_htmltext.htmlescape

if __name__ == "__main__":
    HTMLTest()
