#!/usr/bin/env python
#$HeadURL: svn+ssh://svn/repos/trunk/quixote/setup.py $
#$Id$

# Setup script for Quixote

__revision__ = "$Id$"

import sys, os
from setuptools import setup, Extension
from quixote.qx_distutils import qx_build_py

# a fast htmltext type
htmltext = Extension(name="quixote._c_htmltext",
                     sources=["src/_c_htmltext.c"])

# faster import hook for PTL modules
cimport = Extension(name="quixote.cimport",
                    sources=["src/cimport.c"])

kw = {'name': "Quixote",
      'version': "1.2",
      'description': "A highly Pythonic Web application framework",
      'author': "MEMS Exchange",
      'author_email': "quixote@mems-exchange.org",
      'url': "http://www.mems-exchange.org/software/quixote/",
      'license': "CNRI Open Source License (see LICENSE.txt)",

      'package_dir': {'quixote': 'quixote'},
      'packages': ['quixote',  'quixote.demo', 'quixote.form',
                   'quixote.form2', 'quixote.server'],

      'ext_modules': [],

      'cmdclass': {'build_py': qx_build_py},
      'tests_require': ['webtest']
     }


build_extensions = sys.platform != 'win32'

if build_extensions:
    # The _c_htmltext module requires Python 2.2 features.
    if sys.hexversion >= 0x20200a1:
        kw['ext_modules'].append(htmltext)
    kw['ext_modules'].append(cimport)

    kw['classifiers'] = ['Development Status :: 5 - Production/Stable',
      'Environment :: Web Environment',
      'License :: OSI Approved :: Python License (CNRI Python License)',
      'Intended Audience :: Developers',
      'Operating System :: Unix',
      'Operating System :: Microsoft :: Windows',
      'Operating System :: MacOS :: MacOS X',
      'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
      ]
    kw['download_url'] = ('http://www.mems-exchange.org/software/files'
                          '/quixote/Quixote-%s.tar.gz' % kw['version'])

setup(**kw)
