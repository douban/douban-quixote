#!/www/python/bin/python

# Example driver script for the Quixote demo: publishes the contents of
# the quixote.demo package.

from quixote import enable_ptl, Publisher

# Install the import hook that enables PTL modules.
enable_ptl()

# Create a Publisher instance 
app = Publisher('quixote.demo')

# (Optional step) Read a configuration file
app.read_config("demo.conf")

# Open the configured log files
app.setup_logs()

# Enter the publishing main loop
app.publish_cgi()
