import sys
from quixote.errors import TraversalError

def fact(n):
    f = 1L
    while n > 1:
        f *= n
        n -= 1
    return f

class IntegerUI:

    _q_exports = ["factorial", "prev", "next"]

    def __init__(self, request, component):
        try:
            self.n = int(component)
        except ValueError, exc:
            raise TraversalError(str(exc))

    def factorial(self, request):
        if self.n > 10000:
            sys.stderr.write("warning: possible denial-of-service attack "
                             "(request for factorial(%d))\n" % self.n)
        request.response.set_header("content-type", "text/plain")
        return "%d! = %d\n" % (self.n, fact(self.n))

    def _q_index(self, request):
        return """\
<html>
<head><title>The Number %d</title></head>
<body>
You have selected the integer %d.<p>

You can compute its <a href="factorial">factorial</a> (%d!)<p>

Or, you can visit the web page for the
<a href="../%d/">previous</a> or
<a href="../%d/">next</a> integer.<p>

Or, you can use redirects to visit the
<a href="prev">previous</a> or
<a href="next">next</a> integer.  This makes
it a bit easier to generate this HTML code, but
it's less efficient -- your browser has to go through
two request/response cycles.  And someone still
has to generate the URLs for the previous/next
pages -- only now it's done in the <code>prev()</code>
and <code>next()</code> methods for this integer.<p>

</body>
</html>
""" % (self.n, self.n, self.n, self.n-1, self.n+1)

    def prev(self, request):
        return request.redirect("../%d/" % (self.n-1))

    def next(self, request):
        return request.redirect("../%d/" % (self.n+1))
