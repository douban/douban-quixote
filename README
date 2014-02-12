Quixote
=======

Quixote is yet another framework for developing Web applications in
Python.  The design goals were:

  1) To allow easy development of Web applications where the
     emphasis is more on complicated programming logic than
     complicated templating.

  2) To make the templating language as similar to Python as possible,
     in both syntax and semantics.  The aim is to make as many of the
     skills and structural techniques used in writing regular Python
     code applicable to Web applications built using Quixote.

  3) No magic.  When it's not obvious what to do in
     a certain case, Quixote refuses to guess.

If you view a web site as a program, and web pages as subroutines,
Quixote just might be the tool for you.  If you view a web site as a
graphic design showcase, and each web page as an individual work of art,
Quixote is probably not what you're looking for.

An additional requirement was that the entire system had to be
implementable in a week or two.  The initial version of Quixote was
indeed cranked out in about that time -- thank you, Python!

We've tried to reuse as much existing code as possible:

  * The HTTPRequest and HTTPResponse classes are distantly
    derived from their namesakes in Zope, but we've removed
    huge amounts of Zope-specific code.

  * The quixote.fcgi module is derived from Robin Dunn's FastCGI module,
    available at
      http://alldunn.com/python/#fcgi

Quixote requires Python 2.1 or greater to run.  We only test Quixote
with Python 2.3, but it should still work with 2.1 and 2.2.

For installation instructions, see the doc/INSTALL.txt file (or
http://www.mems-exchange.org/software/quixote/doc/INSTALL.html).

If you're switching to a newer version of Quixote from an older
version, please refer to doc/upgrading.txt for explanations of any
backward-incompatible changes.  


Overview
========

Quixote works by using a Python package to store all the code and HTML
for a Web-based application.  There's a simple framework for
publishing code and objects on the Web, and the publishing loop can be
customized by subclassing the Publisher class.  You can think of it as
a toolkit to build your own smaller, simpler version of Zope,
specialized for your application.

An application using Quixote is a Python package containing .py and
.ptl files.  

webapp/				# Root of package
	__init__.py			
	module1.py
	module2.py
	pages1.ptl
	pages2.ptl

PTL, the Python Template Language, is used to mix HTML with Python code.
More importantly, Python can be used to drive the generation of HTML.
An import hook is defined so that PTL files can be imported just like
Python modules.  The basic syntax of PTL is Python's, with a few small
changes:

def plain [text] barebones_header(title=None,
                                  description=None):
    """
    <html><head>
    <title>%s</title>
    """ % html_quote(str(title))
    if description:
        '<meta name="description" content="%s">' % html_quote(description) 

    '</head><body bgcolor="#ffffff">'

See doc/PTL.txt for a detailed explanation of PTL.


Quick start
===========

For instant gratification, see doc/demo.txt.  This explains how to get
the Quixote demo up and running, so you can play with Quixote without
actually having to write any code.


Documentation
=============

All the documentation is in the doc/ subdirectory, in both text and
HTML.  Or you can browse it online from
  http://www.mems-exchange.org/software/quixote/doc/

Recommended reading:

  demo.txt            getting the Quixote demo up and running, and
                      how the demo works
  programming.txt     the components of a Quixote application: how
                      to write your own Quixote apps
  PTL.txt             the Python Template Language, used by Quixote
                      apps to generate web pages
  web-server.txt      how to configure your web server for Quixote

Optional reading (more advanced or arcane stuff):

  session-mgmt.txt    session management: how to track information
                      across requests
  static-files.txt    making static files and CGI scripts available
  upload.txt          how to handle HTTP uploads with Quixote
  upgrading.txt       info on backward-incompatible changes that may
                      affect applications written with earlier versions
  widgets.txt         reference documentation for the Quixote Widget
                      classes (which underly the form library)
  web-services.txt    how to write web services using Quixote and
                      XML-RPC


Authors, copyright, and license
===============================

Copyright (c) 2000-2003 CNRI.

Quixote was primarily written by Andrew Kuchling, Neil Schemenauer, and
Greg Ward.

Overall, Quixote is covered by the CNRI Open Source License Agreement;
see LICENSE for details.

Portions of Quixote are derived from Zope, and are also covered by the
ZPL (Zope Public License); see ZPL.txt.

Full acknowledgments are in the ACKS file.


Availability, home page, and mailing lists
==========================================

The Quixote home page is:
    http://www.mems-exchange.org/software/quixote/

You'll find the latest stable release there.  The current development
code is also available via CVS; for instructions, see
    http://www.mems-exchange.org/software/quixote/cvs.html

Discussion of Quixote occurs on the quixote-users mailing list:
    http://mail.mems-exchange.org/mailman/listinfo/quixote-users/

To follow development at the most detailed level by seeing every CVS
checkin, join the quixote-checkins mailing list:
    http://mail.mems-exchange.org/mailman/listinfo/quixote-checkins/


-- 
A.M. Kuchling    <akuchlin@mems-exchange.org>
Neil Schemenauer <nascheme@mems-exchange.org>
Greg Ward        <gward@mems-exchange.org>
