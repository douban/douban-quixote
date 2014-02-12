#!/www/python/bin/python

# Example SCGI driver script for the Quixote demo: publishes the contents of
# the quixote.demo package.  To use this script with mod_scgi and Apache
# add the following section of your Apache config file:
#
# <Location "^/qdemo/">
#       SCGIServer 127.0.0.1 4000
#       SCGIHandler On
# </Location>


from scgi.quixote_handler import QuixoteHandler, main
from quixote import enable_ptl, Publisher

class DemoPublisher(Publisher):
    def __init__(self, *args, **kwargs):
        Publisher.__init__(self, *args, **kwargs)

        # (Optional step) Read a configuration file
        self.read_config("demo.conf")

        # Open the configured log files
        self.setup_logs()


class DemoHandler(QuixoteHandler):
    publisher_class = DemoPublisher
    root_namespace = "quixote.demo"
    prefix = "/qdemo"


# Install the import hook that enables PTL modules.
enable_ptl()
main(DemoHandler)
