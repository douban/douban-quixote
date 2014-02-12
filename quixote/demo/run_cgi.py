# This is a simple script that makes it easy to write one file CGI
# applications that use Quixote.  To use, add the following line to the top
# of your CGI script:
#
#  #!/usr/local/bin/python <some_path>/run_cgi.py
#
# Your CGI script becomes the root namespace and you may use PTL syntax
# inside the script.  Errors will go to stderr and should end up in the server
# error log.
#
# Note that this will be quite slow since the script will be recompiled on
# every hit.  If you are using Apache with mod_fastcgi installed you should be
# able to use .fcgi as an extension instead of .cgi and get much better
# performance.  Maybe someday I will write code that caches the compiled
# script on the filesystem. :-)

import sys
import new
from quixote import enable_ptl, ptl_compile, Publisher

enable_ptl()
filename = sys.argv[1]
root_code = ptl_compile.compile_template(open(filename), filename)
root = new.module("root")
root.__file__ = filename
root.__name__ = "root"
exec root_code in root.__dict__
p = Publisher(root)
p.publish_cgi()
