#!/www/python/bin/python
#$HeadURL: svn+ssh://svn/repos/trunk/quixote/ptl_compile.py $
#$Id$

"""
Compile a PTL template.

First the tokens "template" are replaced with "def".  Next, the file is
parsed into a parse tree.  This tree is converted into a modified AST.
It is during this state that the semantics are modified by adding extra
nodes to the tree.  Finally bytecode is generated using the compiler
package.

Note that script/module requires the compiler package.
"""

__revision__ = "$Id$"

import sys
import os
import stat
import symbol
import token
import parser
import re

assert sys.hexversion >= 0x20000b1, 'PTL requires Python 2.0 or newer'

from compiler import pycodegen, transformer, walk
from compiler import ast
from compiler.consts import OP_ASSIGN
if sys.hexversion >= 0x20200b1:
    from compiler import misc, syntax


# magic names inserted into the code
IO_MODULE = "quixote.html"
IO_CLASS = "TemplateIO"
IO_INSTANCE = "_q_output"
HTML_TEMPLATE_PREFIX = "_q_html_template_"
PLAIN_TEMPLATE_PREFIX = "_q_plain_template_"
TEMPLATE_PREFIX = "_q_template_"
MARKUP_MODULE = "quixote.html"
MARKUP_CLASS = "htmltext"
MARKUP_MANGLED_CLASS = "_q_htmltext"

class TemplateTransformer(transformer.Transformer):

    def __init__(self, *args, **kwargs):
        transformer.Transformer.__init__(self, *args, **kwargs)
        self.__template_type = [] # stack, "html", "plain" or None

    def file_input(self, nodelist):
        # Add a "from IO_MODULE import IO_CLASS" statement to the
        # beginning of the module.
        doc = None # self.get_docstring(nodelist, symbol.file_input)

        if sys.hexversion >= 0x02050000:
            io_imp = ast.From(IO_MODULE, [(IO_CLASS, None)], 0)
            markup_imp = ast.From(MARKUP_MODULE, [(MARKUP_CLASS, None)], 0)
        else:
            io_imp = ast.From(IO_MODULE, [(IO_CLASS, None)])
            markup_imp = ast.From(MARKUP_MODULE, [(MARKUP_CLASS, None)])

        markup_assign = ast.Assign([ast.AssName(MARKUP_MANGLED_CLASS,
                                                OP_ASSIGN)],
                                   ast.Name(MARKUP_CLASS))

        # Add an IO_INSTANCE binding for module level expressions (like
        # doc strings).  This instance will not be returned.
        io_instance = ast.CallFunc(ast.Name(IO_CLASS), [])
        io_assign_name = ast.AssName(IO_INSTANCE, OP_ASSIGN)
        io_assign = ast.Assign([io_assign_name], io_instance)

        stmts = [ io_imp, io_assign, markup_imp, markup_assign ]

        for node in nodelist:
            if node[0] != token.ENDMARKER and node[0] != token.NEWLINE:
                self.com_append_stmt(stmts, node)

        return ast.Module(doc, ast.Stmt(stmts))

    def funcdef(self, nodelist):
        if len(nodelist) == 6:
            assert nodelist[0][0] == symbol.decorators
            decorators = self.decorators(nodelist[0][1:])
        else:
            assert len(nodelist) == 5
            decorators = None

        lineno = nodelist[-4][2]
        name = nodelist[-4][1]
        args = nodelist[-3][2]

        if not re.match('_q_((html|plain)_)?template_', name):
            # just a normal function, let base class handle it
            self.__template_type.append(None)
            n = transformer.Transformer.funcdef(self, nodelist)

        else:
            if name.startswith(PLAIN_TEMPLATE_PREFIX):
                name = name[len(PLAIN_TEMPLATE_PREFIX):]
                template_type = "plain"
            elif name.startswith(HTML_TEMPLATE_PREFIX):
                name = name[len(HTML_TEMPLATE_PREFIX):]
                template_type = "html"
            elif name.startswith(TEMPLATE_PREFIX):
                name = name[len(TEMPLATE_PREFIX):]
                template_type = "plain"
            else:
                raise RuntimeError, 'unknown prefix on %s' % name

            self.__template_type.append(template_type)

            # Add "IO_INSTANCE = IO_CLASS()" statement at the beginning of
            # the function and a "return IO_INSTANCE" at the end.
            if args[0] == symbol.varargslist:
                names, defaults, flags = self.com_arglist(args[1:])
            else:
                names = defaults = ()
                flags = 0
            doc = None # self.get_docstring(nodelist[-1])

            # code for function
            code = self.com_node(nodelist[-1])

            # create an instance, assign to IO_INSTANCE
            klass = ast.Name(IO_CLASS)
            args = [ast.Const(template_type == "html")]
            instance = ast.CallFunc(klass, args)
            assign_name = ast.AssName(IO_INSTANCE, OP_ASSIGN)
            assign = ast.Assign([assign_name], instance)

            # return the IO_INSTANCE.getvalue(...)
            func = ast.Getattr(ast.Name(IO_INSTANCE), "getvalue")
            ret = ast.Return(ast.CallFunc(func, []))

            # wrap original function code
            code = ast.Stmt([assign, code, ret])

            if sys.hexversion >= 0x20400a2:
                n = ast.Function(decorators, name, names, defaults, flags, doc,
                                 code)
            else:
                n = ast.Function(name, names, defaults, flags, doc, code)
            n.lineno = lineno

        self.__template_type.pop()
        return n

    def expr_stmt(self, nodelist):
        if not self.__template_type or not self.__template_type[-1]:
            return transformer.Transformer.expr_stmt(self, nodelist)

        # Instead of discarding objects on the stack, call
        # "IO_INSTANCE += obj".
        exprNode = self.com_node(nodelist[-1])
        if len(nodelist) == 1:
            lval = ast.Name(IO_INSTANCE)
            n = ast.AugAssign(lval, '+=', exprNode)
            if hasattr(exprNode, 'lineno'):
                n.lineno = exprNode.lineno
        elif nodelist[1][0] == token.EQUAL:
            nodes = [ ]
            for i in range(0, len(nodelist) - 2, 2):
                nodes.append(self.com_assign(nodelist[i], OP_ASSIGN))
            n = ast.Assign(nodes, exprNode)
            n.lineno = nodelist[1][2]
        else:
            lval = self.com_augassign(nodelist[0])
            op = self.com_augassign_op(nodelist[1])
            n = ast.AugAssign(lval, op[1], exprNode)
            n.lineno = op[2]
        return n

    def atom_string(self, nodelist):
        k = ''
        for node in nodelist:
            k = k + eval(node[1])
        n = ast.Const(k)
        if self.__template_type and self.__template_type[-1] == "html":
            # change "foo" to _q_htmltext("foo")
            n = ast.CallFunc(ast.Name(MARKUP_MANGLED_CLASS), [n])
        return n


_old_template_re = re.compile(r"^([ \t]*) template ([ \t]+)"
                              r" ([a-zA-Z_][a-zA-Z_0-9]*)"   # name of template
                              r" ([ \t]*[\(\\])",
                              re.MULTILINE|re.VERBOSE)

_template_re = re.compile(r"^([ \t]*) def (?:[ \t]+)"                # def
                          r" ([a-zA-Z_][a-zA-Z_0-9]*)"               # <name>
                          r" (?:[ \t]*) \[(plain|html)\] (?:[ \t]*)" # <type>
                          r" (?:[ \t]*[\(\\])",                      # (
                          re.MULTILINE|re.VERBOSE)

def translate_tokens(buf):
    """
    Since we can't modify the parser in the builtin parser module we
    must do token translation here.  Luckily it does not affect line
    numbers.

    template foo(...): -> def _q_template__foo(...):

    def foo [plain] (...): -> def _q_plain_template__foo(...):

    def foo [html] (...): -> def _q_html_template__foo(...):

    XXX This parser is too stupid.  For example, it doesn't understand
    triple quoted strings.
    """
    global _template_re

    # handle new style template declarations
    buf = _template_re.sub(r"\1def _q_\3_template_\2(", buf)

    # change old style template to def
    buf = _old_template_re.sub(r"\1def\2%s\3\4" % TEMPLATE_PREFIX, buf)

    return buf


if sys.hexversion >= 0x20300b1:
    def parse(buf, filename='<string>'):
        buf = translate_tokens(buf)
        try:
            return TemplateTransformer().parsesuite(buf)
        except SyntaxError, e:
            # set the filename attribute
            raise SyntaxError(str(e), (filename, e.lineno, e.offset, e.text))

else:
    # The parser module in Python <= 2.2 can raise ParserError.  Since
    # the ParserError exception is basically useless, we use compile()
    # to generate a better exception.
    def parse(buf, filename='<string>'):
        buf = translate_tokens(buf)
        # compile() and parsermodule don't accept code that is missing a
        # trailing newline.  The Python interpreter seems to add a newline when
        # importing modules so we match that behavior.
        if buf[-1:] != '\n':
            buf += "\n"
        try:
            return TemplateTransformer().parsesuite(buf)
        except (parser.ParserError, SyntaxError):
            import __builtin__
            try:
                __builtin__.compile(buf, filename, 'exec')
            except SyntaxError, exc:
                # Another hack to fix the filename attribute.
                raise SyntaxError(str(exc), (filename, exc.lineno, exc.offset,
                                             exc.text))


PTL_EXT = ".ptl"
PTLC_EXT = ".ptlc"
if sys.hexversion >= 0x20300a1:
    PTLC_MAGIC = "PTLC\x04\x00"
elif sys.hexversion >= 0x20200b1:
    PTLC_MAGIC = "PTLC\x03\x00"
elif sys.hexversion >= 0x20100b1:
    PTLC_MAGIC = "PTLC\x02\x00"
elif sys.hexversion >= 0x20000b1:
    PTLC_MAGIC = "PTLC\x01\x00"
else:
    raise RuntimeError, 'python too old'

class Template(pycodegen.Module):

    if sys.hexversion >= 0x20200b1:
        def _get_tree(self):
            tree = parse(self.source, self.filename)
            misc.set_filename(self.filename, tree)
            syntax.check(tree)
            return tree
    else:
        def compile(self):
            ast = parse(self.source, self.filename)
            gen = pycodegen.ModuleCodeGenerator(self.filename)
            walk(ast, gen, 1)
            self.code = gen.getCode()

    def dump(self, f):
        import marshal
        import stat

        f.write(PTLC_MAGIC)
        mtime = os.stat(self.filename)[stat.ST_MTIME]
        marshal.dump(mtime, f)
        marshal.dump(self.code, f)


def compile_template(input, filename, output=None):
    """compile_template(input, filename, output=None) -> code

    Compile an open file.  If output is not None then the code is written
    with the magic template header.  The code object is returned.
    """
    buf = input.read()
    template = Template(buf, filename)
    template.compile()
    if output:
        template.dump(output)
    return template.code

def compile(inputname, outputname):
    """compile(inputname, outputname)

    Compile a template file.  The new template is writen to outputname.
    """
    input = open(inputname)
    output = open(outputname, "wb")
    try:
        compile_template(input, inputname, output)
    except:
        # don't leave a corrupt .ptlc file around
        output.close()
        os.unlink(outputname)
        raise

def compile_dir(dir, maxlevels=10, force=0):
    """Byte-compile all PTL modules in the given directory tree.
       (Adapted from compile_dir in Python module: compileall.py)

    Arguments (only dir is required):

    dir:       the directory to byte-compile
    maxlevels: maximum recursion level (default 10)
    force:     if true, force compilation, even if timestamps are up-to-date
    """
    print 'Listing', dir, '...'
    try:
        names = os.listdir(dir)
    except os.error:
        print "Can't list", dir
        names = []
    names.sort()
    success = 1
    for name in names:
        fullname = os.path.join(dir, name)
        if os.path.isfile(fullname):
            head, tail = name[:-4], name[-4:]
            if tail == '.ptl':
                cfile = fullname + 'c'
                ftime = os.stat(fullname)[stat.ST_MTIME]
                try:
                    ctime = os.stat(cfile)[stat.ST_MTIME]
                except os.error: ctime = 0
                if (ctime > ftime) and not force:
                    continue
                print 'Compiling', fullname, '...'
                try:
                    ok = compile(fullname, cfile)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except:
                    # XXX compile catches SyntaxErrors
                    if type(sys.exc_type) == type(''):
                        exc_type_name = sys.exc_type
                    else: exc_type_name = sys.exc_type.__name__
                    print 'Sorry:', exc_type_name + ':',
                    print sys.exc_value
                    success = 0
                else:
                    if ok == 0:
                        success = 0
        elif (maxlevels > 0 and name != os.curdir and name != os.pardir and
              os.path.isdir(fullname) and not os.path.islink(fullname)):
            if not compile_dir(fullname, maxlevels - 1, force):
                success = 0
    return success

def main():
    args = sys.argv[1:]
    if not args:
        print "no files to compile"
    else:
        for filename in args:
            path, ext = os.path.splitext(filename)
            compile(filename, path + PTLC_EXT)

if __name__ == "__main__":
    main()

