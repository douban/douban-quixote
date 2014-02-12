"""quixote.mod_python_handler
$HeadURL: svn+ssh://svn/repos/trunk/quixote/mod_python_handler.py $
$Id$

mod_python handler for Quixote.  See the "mod_python configuration"
section of doc/web-server.txt for details.
"""

import sys
from mod_python import apache
from quixote import Publisher, enable_ptl
from quixote.config import Config

class ErrorLog:
    def __init__(self, publisher):
        self.publisher = publisher

    def write(self, msg):
        self.publisher.log(msg)

    def close(self):
        pass

class ModPythonPublisher(Publisher):
    def __init__(self, package, config=None):
        Publisher.__init__(self, package, config)
        self.error_log = self.__error_log = ErrorLog(self) # may be overwritten
        self.setup_logs()
        self.__apache_request = None

    def log(self, msg):
        if self.error_log is self.__error_log:
            try:
                self.__apache_request.log_error(msg)
            except AttributeError:
                apache.log_error(msg)
        else:
            Publisher.log(self, msg)

    def publish_modpython(self, req):
        """publish_modpython() -> None

        Entry point from mod_python.
        """
        self.__apache_request = req
        try:
            self.publish(apache.CGIStdin(req),
                         apache.CGIStdout(req),
                         sys.stderr,
                         apache.build_cgi_env(req))

            return apache.OK
        finally:
            self.__apache_request = None

enable_ptl()

name2publisher = {}

def handler(req):
    opts = req.get_options()
    try:
        package = opts['quixote-root-namespace']
    except KeyError:
        package = None

    try:
        configfile = opts['quixote-config-file']
        config = Config()
        config.read_file(configfile)
    except KeyError:
        config = None

    if not package:
        return apache.HTTP_INTERNAL_SERVER_ERROR

    pub = name2publisher.get(package)
    if pub is None:
        pub = ModPythonPublisher(package, config)
        name2publisher[package] = pub
    return pub.publish_modpython(req)
